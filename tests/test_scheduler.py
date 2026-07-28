"""Engine 2 — the no-double-booking invariant is the whole promise.

Every check re-derives the answer from the solver's OUTPUT rather than trusting
the model, so a bug in the CP-SAT formulation cannot mark its own homework.
"""
from __future__ import annotations

import pandas as pd
import pytest

from engines.geo import distance_km
from engines.scheduler import count_raw_conflicts, solve_schedule
from engines.scheduler.solver import verify_no_double_booking


@pytest.fixture(scope="module")
def solved(platform_data):
    return solve_schedule(platform_data["bookings"], platform_data["resources"],
                          platform_data["projects"])


def test_no_double_bookings(solved):
    assert verify_no_double_booking(solved.assignments) == []


def test_all_bookings_assigned(solved, platform_data):
    assert solved.stats["assigned"] == len(platform_data["bookings"])
    assert solved.stats["unassigned"] == 0


def test_solves_quickly(solved):
    assert solved.stats["solve_seconds"] < 10.0


def test_resource_types_match(solved, platform_data):
    kind = dict(zip(platform_data["resources"]["resource_id"],
                    platform_data["resources"]["type"]))
    for a in solved.assignments:
        assert kind[a["assigned_resource_id"]] == a["resource_type"]


def test_raw_conflicts_detected(platform_data):
    """There must be real contention, else the invariant proves nothing."""
    assert count_raw_conflicts(platform_data["bookings"]) > 0


def test_scarce_pool_degrades_instead_of_failing():
    """With one crane and two overlapping jobs, drop the low-priority one --
    never raise INFEASIBLE, which would be useless to a site manager."""
    bookings = pd.DataFrame([
        {"booking_id": "B1", "project_id": "P1", "project_priority": "high",
         "resource_type": "crane", "requested_start": "2026-03-01T08:00:00",
         "requested_end": "2026-03-01T18:00:00", "task": "lift"},
        {"booking_id": "B2", "project_id": "P1", "project_priority": "low",
         "resource_type": "crane", "requested_start": "2026-03-01T09:00:00",
         "requested_end": "2026-03-01T17:00:00", "task": "lift"},
    ])
    resources = pd.DataFrame([
        {"resource_id": "R1", "type": "crane", "capacity": 1, "home_location": "Almaty"}])
    res = solve_schedule(bookings, resources)

    assert res.stats["assigned"] == 1 and res.stats["unassigned"] == 1
    assert verify_no_double_booking(res.assignments) == []
    # priority must decide the survivor
    assert res.assignments[0]["booking_id"] == "B1"
    assert res.unassigned[0]["booking_id"] == "B2"


def test_prefers_local_resources():
    """Same type, same window: pick the one that doesn't travel."""
    bookings = pd.DataFrame([
        {"booking_id": "B1", "project_id": "P1", "project_priority": "medium",
         "resource_type": "truck", "requested_start": "2026-03-01T08:00:00",
         "requested_end": "2026-03-01T18:00:00", "task": "haul"}])
    resources = pd.DataFrame([
        {"resource_id": "FAR", "type": "truck", "capacity": 1, "home_location": "Atyrau"},
        {"resource_id": "NEAR", "type": "truck", "capacity": 1, "home_location": "Almaty"}])
    projects = pd.DataFrame([{"project_id": "P1", "location": "Almaty"}])
    res = solve_schedule(bookings, resources, projects)
    assert res.assignments[0]["assigned_resource_id"] == "NEAR"
    assert res.assignments[0]["travel_km"] == 0


def test_back_to_back_is_not_an_overlap():
    """A booking ending exactly when the next starts may share a resource."""
    bookings = pd.DataFrame([
        {"booking_id": "B1", "project_id": "P1", "project_priority": "medium",
         "resource_type": "crane", "requested_start": "2026-03-01T08:00:00",
         "requested_end": "2026-03-01T12:00:00", "task": "a"},
        {"booking_id": "B2", "project_id": "P1", "project_priority": "medium",
         "resource_type": "crane", "requested_start": "2026-03-01T12:00:00",
         "requested_end": "2026-03-01T16:00:00", "task": "b"}])
    resources = pd.DataFrame([
        {"resource_id": "R1", "type": "crane", "capacity": 1, "home_location": "Almaty"}])
    res = solve_schedule(bookings, resources)
    assert res.stats["assigned"] == 2
    assert verify_no_double_booking(res.assignments) == []


class TestGeo:
    def test_same_city_is_free(self):
        assert distance_km("Almaty", "Almaty") == 0

    def test_symmetric(self):
        assert distance_km("Almaty", "Astana") == distance_km("Astana", "Almaty")

    def test_unknown_city_does_not_crash(self):
        assert distance_km("Almaty", "Atlantis") > 0
