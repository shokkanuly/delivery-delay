"""Module 2 — multi-site resource scheduling (OR-Tools CP-SAT)."""
from engines.scheduler.solver import ScheduleResult, count_raw_conflicts, solve_schedule

__all__ = ["solve_schedule", "count_raw_conflicts", "ScheduleResult"]
