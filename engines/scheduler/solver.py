"""Multi-site resource scheduler — OR-Tools CP-SAT.

Assigns each booking request to a concrete resource of the matching type such
that no resource is ever double-booked, while minimising travel and spreading
load sensibly.

MODEL
  Variables   assign[b, r] : bool, for every resource r whose type matches
                             booking b. Plus assigned[b] = "b got a resource".
  Constraints (1) each booking uses at most one resource, and exactly one when
                  it can be satisfied;
              (2) NO DOUBLE-BOOKING — per resource, optional intervals with
                  AddNoOverlap. Idiomatic CP-SAT: far better than enumerating
                  overlapping pairs, and it scales.
  Objective   lexicographic-by-weight:
                1. satisfy bookings (weighted by project priority: high > med > low)
                2. minimise travel km (resource home city -> project site)
                3. mild penalty per resource used (consolidation / fewer mobilisations)

WHY optional intervals and an "unassigned" escape hatch: on this dataset the
resource pool comfortably covers peak demand, so everything is satisfiable. But
a scheduler that becomes INFEASIBLE the moment demand spikes is useless in
practice -- with this formulation the solver instead drops the least important
bookings and tells you which, which is what a site manager actually needs.

DELAY-ENGINE COUPLING (the platform's whole point): pass `risk_by_booking` and
bookings whose material is predicted late get their travel cost discounted, so
the solver prefers *locally-based* resources for them -- a cheap, reversible
mobilisation instead of hauling a crane 2,000 km for a slot that may well slip.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from ortools.sat.python import cp_model

from engines.geo import distance_km

PRIORITY_WEIGHT = {"high": 100, "medium": 20, "low": 5}
UNASSIGNED_PENALTY = 10_000       # dominates travel: satisfying a booking wins
RESOURCE_USE_PENALTY = 50         # mild nudge toward fewer distinct resources
RISK_DISCOUNT = 0.5               # travel weight for high-risk bookings


@dataclass
class ScheduleResult:
    assignments: list[dict]                 # booking rows with assigned_resource_id
    unassigned: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _to_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series)


def count_raw_conflicts(bookings: pd.DataFrame) -> int:
    """Pairs of same-type bookings whose time windows overlap.

    This is the *pre-solve* contention count: how many pairs could not share a
    single resource. It is the number the solver has to design around, and the
    honest "before" figure to quote next to the solved result.
    """
    b = bookings.copy()
    b["s"] = _to_ts(b["requested_start"])
    b["e"] = _to_ts(b["requested_end"])
    total = 0
    for _, grp in b.groupby("resource_type"):
        g = grp.sort_values("s").reset_index(drop=True)
        starts, ends = g["s"].tolist(), g["e"].tolist()
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if starts[j] >= ends[i]:
                    break            # sorted by start: no later booking can overlap
                total += 1
    return total


def solve_schedule(
    bookings: pd.DataFrame,
    resources: pd.DataFrame,
    projects: pd.DataFrame | None = None,
    risk_by_booking: dict[str, float] | None = None,
    max_seconds: float = 20.0,
) -> ScheduleResult:
    """Assign resources to bookings without double-booking. See module docstring."""
    bookings = bookings.reset_index(drop=True).copy()
    resources = resources.reset_index(drop=True).copy()
    bookings["_start"] = _to_ts(bookings["requested_start"])
    bookings["_end"] = _to_ts(bookings["requested_end"])

    # Integer time axis in hours from the earliest start (CP-SAT wants ints).
    origin = bookings["_start"].min()
    to_h = lambda t: int((t - origin).total_seconds() // 3600)  # noqa: E731
    bookings["_s"] = bookings["_start"].map(to_h)
    bookings["_e"] = bookings["_end"].map(to_h)

    site_of = {}
    if projects is not None and "location" in projects.columns:
        site_of = dict(zip(projects["project_id"], projects["location"]))

    model = cp_model.CpModel()
    assign: dict[tuple[int, int], cp_model.IntVar] = {}
    intervals_by_resource: dict[int, list] = {ri: [] for ri in resources.index}
    assigned_flags, used_flags = [], {}

    for ri in resources.index:
        used_flags[ri] = model.NewBoolVar(f"used_{ri}")

    obj_terms = []

    for bi, b in bookings.iterrows():
        cands = resources.index[resources["type"] == b["resource_type"]].tolist()
        is_assigned = model.NewBoolVar(f"assigned_{bi}")
        assigned_flags.append(is_assigned)

        lits = []
        for ri in cands:
            v = model.NewBoolVar(f"a_{bi}_{ri}")
            assign[(bi, ri)] = v
            lits.append(v)
            # (2) optional interval -> AddNoOverlap enforces no double-booking
            intervals_by_resource[ri].append(
                model.NewOptionalIntervalVar(
                    b["_s"], max(1, b["_e"] - b["_s"]), b["_e"], v, f"iv_{bi}_{ri}"
                )
            )
            model.AddImplication(v, used_flags[ri])

            # travel cost, discounted when the delivery is predicted at risk
            km = distance_km(
                resources.at[ri, "home_location"],
                site_of.get(b["project_id"], resources.at[ri, "home_location"]),
            )
            w = 1.0
            if risk_by_booking and risk_by_booking.get(b["booking_id"], 0.0) >= 0.66:
                w = RISK_DISCOUNT
            obj_terms.append(int(km * w) * v)

        # (1) at most one resource; assigned flag ties to the choice
        model.Add(sum(lits) == is_assigned) if lits else model.Add(is_assigned == 0)

        # 1. satisfying bookings dominates, weighted by project priority
        prio = PRIORITY_WEIGHT.get(str(b.get("project_priority", "medium")), 20)
        obj_terms.append(UNASSIGNED_PENALTY * prio * (1 - is_assigned))

    for ri, ivs in intervals_by_resource.items():
        if ivs:
            model.AddNoOverlap(ivs)
        obj_terms.append(RESOURCE_USE_PENALTY * used_flags[ri])   # 3. consolidation

    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"Scheduler found no solution (status={solver.StatusName(status)})")

    out, unassigned, total_km, used = [], [], 0, set()
    for bi, b in bookings.iterrows():
        row = {k: v for k, v in b.items() if not k.startswith("_")}
        chosen = next(
            (ri for ri in resources.index
             if (bi, ri) in assign and solver.Value(assign[(bi, ri)])), None
        )
        if chosen is None:
            row["assigned_resource_id"] = None
            row["reason"] = "no resource of matching type available in this window"
            unassigned.append(row)
            continue
        km = distance_km(
            resources.at[chosen, "home_location"],
            site_of.get(b["project_id"], resources.at[chosen, "home_location"]),
        )
        total_km += km
        used.add(resources.at[chosen, "resource_id"])
        row["assigned_resource_id"] = resources.at[chosen, "resource_id"]
        row["travel_km"] = km
        out.append(row)

    return ScheduleResult(
        assignments=out,
        unassigned=unassigned,
        stats={
            "status": solver.StatusName(status),
            "solve_seconds": round(solver.WallTime(), 3),
            "bookings": len(bookings),
            "assigned": len(out),
            "unassigned": len(unassigned),
            "resources_used": len(used),
            "total_travel_km": total_km,
        },
    )


def verify_no_double_booking(assignments: list[dict]) -> list[tuple[str, str]]:
    """Independent check: return overlapping booking pairs sharing a resource.

    Deliberately re-derived from the OUTPUT rather than trusting the solver --
    this is the acceptance test, so it must not depend on the model being right.
    """
    df = pd.DataFrame(assignments)
    if df.empty:
        return []
    df["s"] = _to_ts(df["requested_start"])
    df["e"] = _to_ts(df["requested_end"])
    clashes = []
    for _, grp in df.groupby("assigned_resource_id"):
        g = grp.sort_values("s").reset_index(drop=True)
        for i in range(len(g) - 1):
            if g.at[i + 1, "s"] < g.at[i, "e"]:
                clashes.append((g.at[i, "booking_id"], g.at[i + 1, "booking_id"]))
    return clashes
