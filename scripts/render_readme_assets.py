"""Render the README banner and architecture map as SVG, light and dark.

    python3 -m scripts.render_readme_assets

Colours come from static/design/tokens.css (the design system), so the README
art can never drift from the product. Output: docs/assets/{banner,architecture}-{light,dark}.svg.
GitHub picks the variant with <picture> + prefers-color-scheme.
"""
from __future__ import annotations

import pathlib
import re
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS = ROOT / "static" / "design" / "tokens.css"
OUT = ROOT / "docs" / "assets"
SANS = "Geist, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def palettes() -> dict[str, dict[str, str]]:
    css = TOKENS.read_text()
    split = css.index(':root[data-theme="dark"]')
    tok = lambda block: dict(re.findall(r"--sp-([\w-]+):\s*(#[0-9A-Fa-f]{6})", block))  # noqa: E731
    light = tok(css[:split])
    return {"light": light, "dark": {**light, **tok(css[split:])}}


def text(x, y, s, size=14, fill="#000", weight=400, family=SANS, anchor="start", spacing=0):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'letter-spacing="{spacing}">{escape(s)}</text>')


def mark(x, y, scale, c):
    """The SitePulse mark: a pulse line turning into a rising arrow."""
    return (f'<g transform="translate({x},{y}) scale({scale})" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round" stroke-width="2.8">'
            f'<path d="M4 23h6l3-7 5 13 3.5-9h3.5" stroke="{c["text"]}"/>'
            f'<path d="M25 20 33 11" stroke="{c["accent"]}"/>'
            f'<path d="M27.5 10.5h6v6" stroke="{c["accent"]}"/></g>')


# ─── Banner ──────────────────────────────────────────────────────────────────
def banner(c: dict[str, str]) -> str:
    W, H = 1280, 340
    grid = "".join(f'<path d="M{x} 0V{H}" />' for x in range(40, W, 40)) + \
           "".join(f'<path d="M0 {y}H{W}" />' for y in range(40, H, 40))
    chips, cx = [], 96
    for label in ("DELAY RISK", "EQUIPMENT DISPATCH", "SEQUENCE CHECK"):
        w = len(label) * 8.6 + 28
        chips.append(f'<rect x="{cx}" y="252" width="{w:.0f}" height="30" rx="6" fill="{c["surface"]}" '
                     f'stroke="{c["border-strong"]}"/>' + text(cx + w / 2, 272, label, 12, c["text-2"], 600,
                                                               MONO, "middle", 1.2))
        cx += w + 10
    # A pulse in its own zone (right of the text) that breaks upward into the accent arrow.
    pulse = (f'<path d="M1010 270h34l14-36 22 64 16-44h34l26-26" fill="none" stroke="{c["border-strong"]}" '
             f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
             f'<path d="M1156 228 1222 162" fill="none" stroke="{c["accent"]}" stroke-width="5" stroke-linecap="round"/>'
             f'<path d="M1176 158h48v48" fill="none" stroke="{c["accent"]}" stroke-width="5" '
             f'stroke-linecap="round" stroke-linejoin="round"/>'
             f'<circle cx="1058" cy="234" r="5" fill="{c["warn"]}"/><circle cx="1080" cy="298" r="5" fill="{c["risk"]}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="SitePulse — supplier scorecards from 1C history for one construction site">
<rect width="{W}" height="{H}" rx="18" fill="{c["bg"]}"/>
<g stroke="{c["border"]}" stroke-width="1" opacity="0.55">{grid}</g>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{c["border-strong"]}"/>
{mark(92, 62, 2.4, c)}
{text(196, 122, "SitePulse", 68, c["text"], 650, SANS, spacing=-1.5)}
{text(98, 184, "One site. One export. A supplier scorecard you can inspect.", 24, c["text-2"])}
{text(98, 222, "1C / CSV history · Supplier reliability · Honest model comparison", 15, c["text-3"], 500, MONO)}
{"".join(chips)}
{pulse}
</svg>
'''


# ─── Architecture map ────────────────────────────────────────────────────────
def box(x, y, w, h, title, path, lines, c, accent=False, tag=None):
    stroke = c["accent"] if accent else c["border-strong"]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{c["surface"]}" '
           f'stroke="{stroke}" stroke-width="{2 if accent else 1}"/>',
           text(x + 16, y + 28, title, 16, c["text"], 650)]
    if tag:
        tw = len(tag) * 7.2 + 16
        out.append(f'<rect x="{x + w - tw - 12}" y="{y + 36}" width="{tw:.0f}" height="20" rx="5" '
                   f'fill="none" stroke="{c["accent"]}"/>' +
                   text(x + w - tw / 2 - 12, y + 50, tag, 11, c["accent"], 600, MONO, "middle", 0.8))
    if path:
        out.append(text(x + 16, y + 50, path, 12.5, c["accent"] if accent else c["info"], 500, MONO))
    for i, line in enumerate(lines):
        out.append(text(x + 16, y + (74 if path else 54) + i * 20, line, 13.5, c["text-2"]))
    return "".join(out)


def row(x, y, w, h, items, c, gap=12, weights=None):
    weights = weights or [1] * len(items)
    unit = (w - gap * (len(items) - 1)) / sum(weights)
    out, cx = [], x
    for item, wt in zip(items, weights):
        bw = unit * wt
        out.append(box(cx, y, bw, h, *item[:3], c, **(item[3] if len(item) > 3 else {})))
        cx += bw + gap
    return "".join(out)


def band(x, y, w, h, num, label, note, c):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{c["surface-2"]}" '
            f'stroke="{c["border"]}"/>' +
            text(x + 20, y + 28, f"{num}  {label}", 13, c["text"], 700, MONO, spacing=1.5) +
            text(x + w - 20, y + 28, note, 12.5, c["text-3"], 500, MONO, "end"))


def down_arrows(x, w, y1, y2, label, c):
    out = []
    for frac in (0.1, 0.9):          # clear of the centred label pill
        ax = x + w * frac
        out.append(f'<path d="M{ax} {y1 + 4}V{y2 - 8}" stroke="{c["text-3"]}" stroke-width="1.6"/>'
                   f'<path d="M{ax - 6} {y2 - 14}l6 8 6-8" fill="none" stroke="{c["text-3"]}" stroke-width="1.6"/>')
    mid = (y1 + y2) / 2 + 5
    lw = len(label) * 7.4 + 24
    out.append(f'<rect x="{x + w / 2 - lw / 2}" y="{mid - 16}" width="{lw:.0f}" height="24" rx="12" '
               f'fill="{c["bg"]}" stroke="{c["border"]}"/>' +
               text(x + w / 2, mid, label, 12, c["text-2"], 500, MONO, "middle"))
    return "".join(out)


def lane(x, y, w, h, title, steps, c, loop=False):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="none" stroke="{c["border-strong"]}" '
           f'stroke-dasharray="5 5"/>', text(x + w / 2, y + 28, title, 13, c["text"], 700, MONO, "middle", 1.5)]
    step_h, top = 92, y + 48
    gap = (h - 64 - step_h * len(steps)) / max(1, len(steps) - 1)
    for i, (head, sub) in enumerate(steps):
        sy = top + i * (step_h + gap)
        out.append(f'<rect x="{x + 12}" y="{sy}" width="{w - 24}" height="{step_h}" rx="8" fill="{c["surface"]}" '
                   f'stroke="{c["border"]}"/>' + text(x + 24, sy + 26, head, 12.5, c["accent"], 600, MONO))
        for j, line in enumerate(sub):
            out.append(text(x + 24, sy + 48 + j * 18, line, 12.5, c["text-2"]))
        if i < len(steps) - 1:
            ay1, ay2 = sy + step_h, sy + step_h + gap
            out.append(f'<path d="M{x + w / 2} {ay1 + 3}V{ay2 - 6}" stroke="{c["text-3"]}" stroke-width="1.6"/>'
                       f'<path d="M{x + w / 2 - 5} {ay2 - 11}l5 7 5-7" fill="none" stroke="{c["text-3"]}" stroke-width="1.6"/>')
    if loop:
        lx, y_first, y_last = x + w - 6, top + 46, top + (len(steps) - 1) * (step_h + gap) + 46
        out.append(f'<path d="M{lx - 6} {y_last}h6V{y_first}h-6" fill="none" stroke="{c["accent"]}" '
                   f'stroke-width="1.6" stroke-dasharray="4 4"/>')
    return "".join(out)


def architecture(c: dict[str, str]) -> str:
    W, H = 1280, 1010
    LX, LW = 32, 196            # left lane: ingest
    RX, RW = 1052, 196          # right lane: evidence loop
    CX, CW = 248, 784           # centre: the four layers
    B1, B2, B3, B4 = (118, 168), (322, 168), (536, 212), (802, 168)   # (y, h)
    p = 16
    parts = [
        f'<rect width="{W}" height="{H}" rx="18" fill="{c["bg"]}"/>',
        mark(32, 26, 1.25, c),
        text(92, 60, "SitePulse — architecture map", 26, c["text"], 650, spacing=-0.4),
        text(92, 86, "Four layers. Each layer only calls the one below it; domain engines never import the web stack.",
             14, c["text-2"]),
        # 1 · interfaces
        band(CX, B1[0], CW, B1[1], "01", "INTERFACES", "what people touch", c),
        row(CX + p, B1[0] + 44, CW - 2 * p, B1[1] - 60, [
            ("SitePulse Console", "static/index.html", ["Served by the API itself", "Light theme · mobile-ready"],
             {"accent": True, "tag": "PRODUCT"}),
            ("Analyst view", "dashboard/app.py", ["Streamlit · model ops", "Internal, not customer-facing"]),
            ("Any HTTP client", "/docs  (OpenAPI)", ["Scripts, ERP connectors", "Same JSON contract"]),
        ], c),
        down_arrows(CX, CW, B1[0] + B1[1], B2[0], "HTTP + JSON · contracts in api/schemas.py", c),
        # 2 · API
        band(CX, B2[0], CW, B2[1], "02", "API  ·  FastAPI", "api/", c),
        row(CX + p, B2[0] + 44, CW - 2 * p, B2[1] - 60, [
            ("Routers", "api/routers/", ["predict · schedule · validate", "projects · business · monitoring"]),
            ("Access control", "api/security.py", ["X-API-Key on admin routes", "Explicit CORS origins"]),
            ("Served model", "api/model_store.py", ["Cached model artifact", "Supplier coverage → /health"]),
        ], c, weights=[1.25, 1, 1]),
        down_arrows(CX, CW, B2[0] + B2[1], B3[0], "plain Python calls · DataFrames in, dicts out", c),
        # 3 · engines
        band(CX, B3[0], CW, B3[1], "03", "DOMAIN ENGINES", "pure Python, no web imports", c),
        row(CX + p, B3[0] + 44, CW - 2 * p, B3[1] - 60, [
            ("1 · Delay risk", "ml/", ["Gradient boosting", "Empirical-Bayes priors", "Top risk drivers"],
             {"accent": True}),
            ("2 · Dispatch", "engines/scheduler/", ["OR-Tools CP-SAT", "No unit double-booked", "Prefers nearby units"]),
            ("3 · Sequence", "engines/validator/", ["Phase-date rules", "+ Isolation Forest", "anomaly layer"]),
            ("Economics", "business/", ["ROI scenarios", "Unit economics", "Every pitch number"]),
        ], c),
        down_arrows(CX, CW, B3[0] + B3[1], B4[0], "read_reference(): database first, CSV fallback", c),
        # 4 · data
        band(CX, B4[0], CW, B4[1], "04", "DATA", "store of record", c),
        row(CX + p, B4[0] + 44, CW - 2 * p, B4[1] - 60, [
            ("Database", "db/  (SQLAlchemy)", ["SQLite locally, Postgres in", "Docker · 11 tables"]),
            ("Reference data", "data/synthetic/", ["Seed CSVs (fictional sites)", "One source for seed + train"]),
            ("Model artifact", "ml/artifacts/", ["model.joblib + feature", "snapshot + data_source"]),
        ], c),
        # side lanes
        lane(LX, B2[0], LW, B4[0] + B4[1] - B2[0], "INGEST", [
            ("1C / ERP export", ["Delivery receipts as CSV"]),
            ("ml/ingest.py", ["Validate schema,", "parse dates"]),
            ("db.seed", ["Load the database"]),
            ("ml.train", ["Same file → model", "knows every supplier"]),
        ], c),
        lane(RX, B2[0], RW, B4[0] + B4[1] - B2[0], "EVIDENCE LOOP", [
            ("POST /predict", ["Score a delivery"]),
            ("prediction_log", ["Every served score,", "with model version"]),
            ("POST /outcomes", ["What really happened", "(admin key)"]),
            ("GET /accuracy", ["Realized precision", "and recall"]),
        ], c, loop=True),
        text(W / 2, H - 26, "Generated by scripts/render_readme_assets.py from static/design/tokens.css",
             12, c["text-3"], 500, MONO, "middle"),
    ]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="SitePulse architecture: interfaces, API, domain engines and data layers, with ingest and '
            f'evidence-loop flows">\n' + "\n".join(parts) + "\n</svg>\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, c in palettes().items():
        (OUT / f"banner-{theme}.svg").write_text(banner(c))
        (OUT / f"architecture-{theme}.svg").write_text(architecture(c))
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
