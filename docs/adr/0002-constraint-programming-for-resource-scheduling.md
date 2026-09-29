# ADR 0002: Constraint Programming (OR-Tools CP-SAT) for Resource Scheduling

## Context & Problem Statement
Heavy construction site equipment (Tower Cranes, Concrete Boom Pumps, Hoists, Material Unload Bays) must be allocated across dozens of concurrent subcontractor requests. In practice, subcontractors submit overlapping requests for the same time slots, creating severe logistical gridlock.

Alternative scheduling approaches include:
- **Greedy Heuristics (First-Come First-Served):** Highly sub-optimal; locks in low-priority bookings and fragments available windows.
- **Mixed-Integer Linear Programming (MILP):** Disjunctive non-overlap formulations scale poorly with time index discretizations.
- **Genetic Algorithms:** Stochastic, non-deterministic, and cannot mathematically prove the absence of overlapping bookings.

## Decision
We utilize Google OR-Tools **CP-SAT solver** using interval variables (`NewIntervalVar`) and the native cumulative global constraint `AddNoOverlap`:
1. Each booking is modeled as an optional interval over eligible resources of the requested equipment type.
2. An exact `AddNoOverlap` constraint is enforced across all intervals mapped to the same physical machine.
3. The objective function minimizes makespan while prioritizing high-priority projects and local equipment availability.
4. Upstream delivery delay risk (from Engine 1) is incorporated into interval penalties to favor resilient, buffered allocations.

## Consequences & Trade-offs
### Positive
- **Provable Invariant:** Mathematically guarantees 0 double-bookings on every physical resource.
- **Fast Execution:** Solves 250+ booking requests across multi-week horizons in <0.3 seconds.
- **Declarative Extensibility:** New site constraints (e.g. noise curfews, operator shift changes) can be added as pure mathematical constraints without rewriting greedy scheduling loops.

### Negative / Mitigations
- **Solver Timeouts on Extreme Scales:** Very large instances (thousands of slots) could exceed interactive timeout thresholds.
- *Mitigation:* The solver configuration sets explicit time limits and returns the best feasible solution found within the allotted deadline.
