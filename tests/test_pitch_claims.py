"""Pitch-claim drift guard.

Current product claims must match the evidence. Legacy financial scenarios
stay reproducible, without forcing retired prices into the current pitch. CHANGELOG/ROADMAP are history logs
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
    "docs/JUDGES.md", "docs/RESEARCH.md",
    "docs/ARCHITECTURE.md", "docs/RUNBOOK.md",
    "dashboard/app.py", "static/index.html",
]

# Retired claims: contradicted by the code or by each other.
BANNED = [
    r"10 interviews: 7",
    r"What 10 interviewees reported",
    r"Interview Quotes \(Astana",
    r"Site Superintendent, 22-Story",
    r"Interviewees reported booking clashes",
    r"crane uptime vs unoptimized",
    r"4\.2% vs yesterday",
    r"Confirm >\$50k/site monthly savings",
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
    r"100% detection|Validation Accuracy",  # same tautology, other wording
    r"Key-Secured|Authorized Contractor|Restricted \(Operator",  # security the code does not enforce
    r"0\.858|0\.831|\+0\.126",          # metrics of the old simulator-trained model, not the served one
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


def test_archived_scenarios_remain_numerically_reproducible():
    archive = _text("docs/archive/economics-scenarios.md")
    missing = {k: v for k, v in economics.headline().items() if v not in archive}
    assert not missing, f"archived scenarios drifted: {missing}"
    assert "not the current offer" in archive


def test_current_pitch_does_not_reintroduce_retired_dollar_pricing():
    for rel in ("README.md", "docs/INVESTOR_DECK.md", "docs/PILOT_PROPOSAL.md", "static/index.html"):
        text = _text(rel)
        for price in ("$15,000", "$3,500", "$4,800"):
            assert price not in text, f"{rel}: legacy scenario price shown as current offer"


def test_no_static_content_posing_as_live():
    for rel in ("static/index.html", "dashboard/app.py"):
        text = _text(rel)
        for fake in ("Aidos", "Kassenov", "12 March 2025", "12 Mar 2025", "Today · Central Hub"):
            assert fake not in text, f"{rel}: {fake}"
