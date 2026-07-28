"""Label definition and the real-data ingestion seam."""
from __future__ import annotations

import pandas as pd
import pytest

from ml.ingest import DeliveryCSVError, load_deliveries_csv
from ml.labeling import LabelConfig, add_labels


def _row(material, promised, actual):
    return {"supplier_id": "S1", "project_site": "site", "material_type": material,
            "route_type": "urban", "quantity": 10,
            "order_date": pd.Timestamp("2026-01-01"),
            "promised_date": pd.Timestamp(promised),
            "actual_date": pd.Timestamp(actual)}


class TestGraceWindows:
    def test_concrete_is_late_after_one_day(self):
        """Zero grace: ready-mix concrete is late the moment it misses the day."""
        df = add_labels(pd.DataFrame([_row("ready_mix_concrete", "2026-02-01", "2026-02-02")]))
        assert df.loc[0, "is_late"] == 1

    def test_tiles_tolerate_three_days(self):
        df = add_labels(pd.DataFrame([_row("tiles_finishing", "2026-02-01", "2026-02-04")]))
        assert df.loc[0, "is_late"] == 0, "3 days is within the finishing grace window"

    def test_tiles_late_on_the_fourth_day(self):
        df = add_labels(pd.DataFrame([_row("tiles_finishing", "2026-02-01", "2026-02-05")]))
        assert df.loc[0, "is_late"] == 1

    def test_unknown_material_uses_default_grace(self):
        cfg = LabelConfig(default_grace_days=1)
        df = add_labels(pd.DataFrame([_row("moon_rock", "2026-02-01", "2026-02-03")]), cfg)
        assert df.loc[0, "is_late"] == 1

    def test_early_delivery_is_not_late(self):
        df = add_labels(pd.DataFrame([_row("cement", "2026-02-10", "2026-02-01")]))
        assert df.loc[0, "is_late"] == 0
        assert df.loc[0, "delay_days"] == -9


class TestIngest:
    def _csv(self, tmp_path, text):
        p = tmp_path / "d.csv"
        p.write_text(text)
        return p

    def test_missing_columns_raise(self, tmp_path):
        p = self._csv(tmp_path, "supplier_id,material_type\nS1,cement\n")
        with pytest.raises(DeliveryCSVError, match="missing required columns"):
            load_deliveries_csv(p)

    def test_drops_bad_rows_but_keeps_good(self, tmp_path):
        p = self._csv(tmp_path,
            "supplier_id,material_type,route_type,quantity,order_date,promised_date,actual_date\n"
            "S1,cement,urban,10,2026-01-01,2026-01-10,2026-01-12\n"
            "S2,cement,urban,-5,2026-01-01,2026-01-10,2026-01-12\n"      # bad quantity
            "S3,cement,urban,10,not-a-date,2026-01-10,2026-01-12\n")     # bad date
        out = load_deliveries_csv(p)
        assert len(out) == 1 and out.loc[0, "supplier_id"] == "S1"

    def test_project_site_defaults_when_absent(self, tmp_path):
        p = self._csv(tmp_path,
            "supplier_id,material_type,route_type,quantity,order_date,promised_date,actual_date\n"
            "S1,cement,urban,10,2026-01-01,2026-01-10,2026-01-12\n")
        assert load_deliveries_csv(p).loc[0, "project_site"] == "unknown"

    def test_scoring_only_file_needs_no_actual_date(self, tmp_path):
        p = self._csv(tmp_path,
            "supplier_id,material_type,route_type,quantity,order_date,promised_date\n"
            "S1,cement,urban,10,2026-01-01,2026-01-10\n")
        assert len(load_deliveries_csv(p, require_actual=False)) == 1

    def test_all_rows_invalid_raises(self, tmp_path):
        p = self._csv(tmp_path,
            "supplier_id,material_type,route_type,quantity,order_date,promised_date,actual_date\n"
            "S1,cement,urban,0,bad,bad,bad\n")
        with pytest.raises(DeliveryCSVError, match="No valid rows"):
            load_deliveries_csv(p)
