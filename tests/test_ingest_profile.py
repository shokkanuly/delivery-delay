"""Stage 1 (docs/plans/mvp-reshape.md): the 1C/Excel column profile.

Covers the Done when of Stage 1: the fixture loads to canonical columns; a
file missing a required column fails with the Russian names of the missing
columns; the quality report counts bad dates and duplicates.
"""
from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from ml.ingest import CANONICAL_COLUMNS, DeliveryCSVError, load_export, sniff_csv

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "1c_export_cp1251.csv"


class TestFixtureLoadsToCanonicalColumns:
    def test_not_valid_utf8(self):
        """The fixture must actually exercise the cp1251 fallback, not just
        happen to decode as utf-8 by luck."""
        with pytest.raises(UnicodeDecodeError):
            FIXTURE.read_bytes().decode("utf-8")

    def test_loads_and_columns_are_canonical(self):
        df, _ = load_export(FIXTURE)
        assert list(df.columns) == [c for c in CANONICAL_COLUMNS if c in df.columns]
        assert set(df.columns) >= {"supplier_id", "material_type", "route_type",
                                   "quantity", "order_date", "promised_date", "actual_date"}

    def test_russian_headers_mapped_and_values_typed(self):
        df, _ = load_export(FIXTURE)
        row = df.iloc[0]
        assert row["supplier_id"] == "ТОО СтройМатериал"
        assert row["material_type"] == "Арматура"
        assert isinstance(row["order_date"], pd.Timestamp)
        assert row["quantity"] == 1200.0          # "1 200" -> thousand-separator space stripped

    def test_route_type_defaults_to_unknown_and_is_reported(self):
        """route_type has no 1C column -- it must default, and the default
        must be visible in the report, never passed off as real data."""
        df, report = load_export(FIXTURE)
        assert set(df["route_type"]) == {"unknown"}
        assert report.route_type_defaulted == report.rows_total


class TestQualityReport:
    def test_counts_bad_dates(self):
        """Row with actual_date='не прибыло' and row with promised_date
        '32.13.2026' (invalid) are both unparseable -- both counted, both
        dropped."""
        _, report = load_export(FIXTURE)
        assert report.bad_dates == 2

    def test_counts_duplicates(self):
        """Fixture row 4 is an exact duplicate of row 1."""
        _, report = load_export(FIXTURE)
        assert report.duplicates == 1

    def test_kept_dropped_total_is_consistent(self):
        df, report = load_export(FIXTURE)
        assert report.rows_total == 12
        assert len(df) == report.rows_kept
        assert report.rows_dropped == report.rows_total - report.rows_kept
        # duplicate(1) + bad actual_date(1) + bad promised_date(1) + blank actual_date(1)
        assert report.rows_dropped == 4

    def test_flags_promised_before_order_without_dropping(self):
        """Row 10: promised_date (10.03) before order_date (15.03) -- a real
        data-entry smell, kept and flagged, not silently dropped."""
        df, report = load_export(FIXTURE)
        assert report.promised_before_order == 1
        flagged = df[df["promised_date"] < df["order_date"]]
        assert len(flagged) == 1

    def test_summary_mentions_every_nonzero_count(self):
        _, report = load_export(FIXTURE)
        text = report.summary()
        assert "8/12" in text
        assert "unparseable" in text
        assert "duplicate" in text
        assert "route_type" in text


class TestMissingRequiredColumn:
    def test_fails_with_russian_column_name(self):
        """A file missing a required column must fail with the Russian name
        of what's missing, not just the English canonical name -- the person
        reading the error is looking at their own 1C export."""
        raw = ("Поставщик;Номенклатура;Дата заказа;Плановая дата поставки;Дата поступления\n"
              "A;B;01.01.2026;05.01.2026;06.01.2026\n").encode("utf-8")
        with pytest.raises(DeliveryCSVError, match="Количество"):
            load_export(raw)

    def test_lists_every_missing_column(self):
        raw = "Поставщик;Количество\nA;5\n".encode("utf-8")
        with pytest.raises(DeliveryCSVError) as exc:
            load_export(raw)
        msg = str(exc.value)
        assert "Номенклатура" in msg
        assert "Дата заказа" in msg
        assert "Плановая дата" in msg


class TestSniffCsv:
    def test_detects_cp1251_and_semicolon(self):
        text, delimiter = sniff_csv(FIXTURE.read_bytes())
        assert delimiter == ";"
        assert "Поставщик" in text

    def test_detects_utf8_sig_and_comma(self):
        raw = "a,b,c\n1,2,3\n".encode("utf-8-sig")
        text, delimiter = sniff_csv(raw)
        assert delimiter == ","
        assert text.startswith("a,b,c")


class TestRequireActualFalse:
    def test_scoring_only_export_keeps_rows_with_no_actual_date(self):
        """An export of orders not yet delivered has no actual_date at all --
        require_actual=False must not drop every row for it."""
        raw = ("Поставщик;Номенклатура;Дата заказа;Плановая дата поставки;Количество\n"
              "A;Кирпич;01.03.2026;15.03.2026;100\n").encode("utf-8")
        df, report = load_export(raw, require_actual=False)
        assert len(df) == 1
        assert report.rows_kept == 1
