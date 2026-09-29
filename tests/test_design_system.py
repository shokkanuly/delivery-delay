"""DESIGN.md guard rails: both UIs draw colour and type from the shared token
file, use only the claim-badge vocabulary, and carry no partner branding."""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS = ROOT / "static" / "design" / "tokens.css"
UIS = ["dashboard/app.py", "static/index.html"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def _tok(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--sp-[\w-]+):\s*([^;]+);", block))


def test_both_themes_define_the_same_colours():
    css = TOKENS.read_text()
    light = _tok(css[css.index(":root {"):css.index(':root[data-theme="dark"]')])
    dark = _tok(css[css.index(':root[data-theme="dark"]'):])
    colours = {k for k, v in light.items() if v.startswith(("#", "rgba"))}
    assert set(dark) <= set(light)
    assert colours <= set(dark), colours - set(dark)


def test_motion_respects_reduced_motion():
    css = TOKENS.read_text()
    assert "prefers-reduced-motion: reduce" in css
    for anim in re.findall(r"animation:\s*([\w-]+)", css):
        assert anim.startswith("sp-"), anim


@pytest.mark.parametrize("rel", UIS)
def test_ui_uses_shared_tokens_not_raw_colours(rel):
    text = (ROOT / rel).read_text()
    assert "tokens.css" in text
    raw = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", text)} - {"#FFFFFF"}
    assert not raw, f"{rel} has raw colours: {sorted(raw)}"


@pytest.mark.parametrize("rel", UIS)
def test_ui_fonts_and_emoji(rel):
    text = (ROOT / rel).read_text()
    assert not re.search(r"'Inter'|Instrument Serif|Georgia", text)
    assert not EMOJI.search(text), EMOJI.findall(text)


@pytest.mark.parametrize("rel", UIS)
def test_only_the_badge_vocabulary(rel):
    labels = set(re.findall(r'class="(?:badge-guarantee|badge-estimate|sp-badge[^"]*)"[^>]*>([^<]+)<',
                            (ROOT / rel).read_text()))
    allowed = {"Correctness Invariant", "Estimate", "Statistical Estimate", "Synthetic Data",
               "Sanity Check", "Operating Input", "Dataset Prevalence"}
    assert labels <= allowed, labels - allowed


def test_streamlit_theme_mirrors_dark_tokens():
    css = TOKENS.read_text()
    dark = _tok(css[css.index(':root[data-theme="dark"]'):])
    toml = (ROOT / ".streamlit" / "config.toml").read_text()
    assert f'primaryColor = "{dark["--sp-accent"]}"' in toml
    assert f'backgroundColor = "{dark["--sp-bg"]}"' in toml
    assert f'secondaryBackgroundColor = "{dark["--sp-surface"]}"' in toml


def test_brand_marks_exist_and_are_unbranded():
    for name in ("logo.svg", "mark.svg", "icon.png"):
        assert (ROOT / "static" / "design" / name).exists()
    assert "BI" not in (ROOT / "static" / "design" / "logo.svg").read_text().split("aria-label")[1][:20]


@pytest.mark.parametrize("rel", UIS)
def test_layout_rules(rel):
    text = (ROOT / rel).read_text()
    assert "100vh" not in text, "use 100dvh"
    assert not re.search(r"rgba\(0,\s*0,\s*0", text), "shadows are Zinc-tinted, never pure black"
    assert not re.search(r"seamless|elevate|unleash|next-gen|AI engine", text, re.IGNORECASE)


def test_console_is_responsive_and_feature_rows_are_asymmetric():
    html = (ROOT / "static" / "index.html").read_text()
    assert "@media (max-width: 767px)" in html
    engines = html[html.index(".engines-row {"):]
    assert "repeat(3, 1fr)" not in engines[:engines.index("}")]
