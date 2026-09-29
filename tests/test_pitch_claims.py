"""Pitch-claim drift guard.

Every figure a juror sees must come from business/economics.py, and claims
the repo cannot back must not come back. CHANGELOG/ROADMAP are history logs
and ADRs are engineering records, so they are not scanned.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from business import economics

ROOT = pathlib.Path(__file__).resolve().parent.parent
PITCH_FILES = [
    "README.md", "CONTRIBUTING.md",
    "docs/INVESTOR_DECK.md", "docs/PILOT_PROPOSAL.md", "docs/PRD.md",
    "docs/ARCHITECTURE.md", "docs/RUNBOOK.md",
    "dashboard/app.py", "static/index.html",
]

# Retired claims: contradicted by the code or by each other.
BANNED = [
    r"piloting with BI Group",          # no signed pilot exists
    r"BI[ -]?(GROUP )?SITE-PULSE",      # partner brand in the product name
    r"\$621", r"621,000", r"221\.8",    # old ROI, from a formula that no longer exists
    r"\$290,?000|\$290k",               # concrete figure 10x the interview figure
    r"19\.4 ?: ?1",                     # LTV:CAC from un-margined LTV
    r"140%",                            # retention claimed with no revenue
    r">\s?14\s?[×x]",                   # fourth ROI definition
    r"83%",                             # not a possible fraction of 7 interviews
    r"Target Scor|Pre-Fix Score",       # self-graded rubric table
    r"100% [Rr]ecall",                  # tautological on rule-generated labels
]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", PITCH_FILES)
def test_no_retired_claims(rel):
    text = _text(rel)
    hits = [p for p in BANNED if re.search(p, text, re.IGNORECASE)]
    assert not hits, f"{rel} still contains: {hits}"


@pytest.mark.parametrize("rel", PITCH_FILES)
def test_lightgbm_only_named_as_the_optional_swap(rel):
    """The model is scikit-learn HistGradientBoosting; LightGBM is optional."""
    for line in _text(rel).splitlines():
        if "lightgbm" in line.lower():
            assert re.search(r"optional|drop-in|swap", line, re.IGNORECASE), line.strip()


def test_deck_quotes_every_headline_figure():
    deck = _text("docs/INVESTOR_DECK.md")
    missing = {k: v for k, v in economics.headline().items() if v not in deck}
    assert not missing, f"deck does not quote economics.headline(): {missing}"


def test_readme_quotes_the_core_figures():
    readme = _text("README.md")
    h = economics.headline()
    for key in ("price_range", "pilot_fee", "value_base", "multiple_base",
                "value_conservative", "multiple_conservative"):
        assert h[key] in readme, f"README missing {key}={h[key]!r}"
