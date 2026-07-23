"""Problem 4 -- Nail down the label before anything else.

"Late" is not a universal constant. Ready-mix concrete is late the moment it
misses the day; finishing tiles have days of slack. So the label is defined by a
per-material *grace window*, and everything downstream keys off `is_late`.

Design choices:
  * Default is BINARY (late vs. not-late). With only hundreds-to-thousands of
    rows, splitting into early/on-time/late starves each class (see Problem 1),
    so binary is the honest default. `mode="three_class"` is available when you
    have the volume.
  * "late" is the positive class -- it is the actionable one (you intervene on
    deliveries predicted to slip).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Business-defined tolerance per material, in days. Tune WITH the BI Group site
# teams -- this single table encodes how much lateness actually causes pain.
DEFAULT_GRACE_DAYS = {
    "ready_mix_concrete": 0,   # perishable, same-day or it's late
    "cement": 1,
    "rebar": 2,
    "insulation": 2,
    "bricks": 3,
    "tiles_finishing": 3,      # finishing trades, more schedule float
}


@dataclass
class LabelConfig:
    mode: str = "binary"                     # "binary" | "three_class"
    default_grace_days: int = 1              # fallback for unknown materials
    grace_days_by_material: dict = field(
        default_factory=lambda: dict(DEFAULT_GRACE_DAYS)
    )
    early_grace_days: int = 2                # only used when mode="three_class"

    def grace_for(self, material: str) -> int:
        return self.grace_days_by_material.get(material, self.default_grace_days)


def add_labels(df: pd.DataFrame, config: LabelConfig | None = None) -> pd.DataFrame:
    """Add `delay_days`, `is_late` (and `delivery_status` in three_class mode)."""
    config = config or LabelConfig()
    out = df.copy()
    out["delay_days"] = (out["actual_date"] - out["promised_date"]).dt.days
    grace = out["material_type"].map(config.grace_for).fillna(config.default_grace_days)
    out["is_late"] = (out["delay_days"] > grace).astype(int)

    if config.mode == "three_class":
        out["delivery_status"] = np.select(
            [out["delay_days"] > grace, out["delay_days"] < -config.early_grace_days],
            ["late", "early"],
            default="on_time",
        )
    return out


if __name__ == "__main__":
    from ml.data_sim import generate_deliveries

    d = add_labels(generate_deliveries())
    rate = d["is_late"].mean()
    print(f"Late rate: {rate:.1%}  (n={len(d)})")
    print(d.groupby("material_type")["is_late"].mean().sort_values().to_string())
