"""Shared access to the bundled synthetic reference data.

Master data (resources, projects, phase map, build programme) is read through
here so every engine sees ONE source of truth rather than re-reading CSVs from
scattered paths. Frames are cached — they're small and static per process.

Real-data cutover: point `SYNTHETIC_DIR` at the real export directory, or swap
`read_synthetic` for a DB query; nothing else in the API changes.
"""
from __future__ import annotations

import pathlib
from functools import lru_cache

import pandas as pd

SYNTHETIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "synthetic"


@lru_cache(maxsize=16)
def _read_cached(name: str) -> pd.DataFrame:
    return pd.read_csv(SYNTHETIC_DIR / name)


def read_synthetic(name: str) -> pd.DataFrame:
    """Return a defensive copy of a bundled reference CSV."""
    return _read_cached(name).copy()
