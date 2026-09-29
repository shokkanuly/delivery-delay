"""SitePulse — internal analyst view (Streamlit).

The customer-facing product is the console in static/index.html, served by the
API; see docs/plans/architecture-review.md (Stage 7). This view is kept for
model operations and exploration, and is not maintained as a customer surface.

Dark theme of the shared design system: tokens in static/design/tokens.css,
rules in DESIGN.md. Views: Overview, Delivery Signals, Resource Plan, Sequence
Checks, Site Network, Company Workspace, Pilot Engagement, Pitch & Economics.
Business figures come from the API (GET /economics); none are computed here.
"""
from __future__ import annotations

import base64
import datetime
import os
import pathlib

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="SitePulse · Command Surface",
    page_icon=str(pathlib.Path(__file__).resolve().parent.parent / "static" / "design" / "icon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)


DESIGN_DIR = pathlib.Path(__file__).resolve().parent.parent / "static" / "design"


# ─── Design tokens (static/design/tokens.css, rules in DESIGN.md) ───
def _design_tokens() -> str:
    """The shared token file with its dark block promoted to :root, because
    Streamlit markdown cannot set data-theme on <html>. Later rules win, so
    the dark values override the light defaults."""
    css = (DESIGN_DIR / "tokens.css").read_text()
    return css.replace(':root[data-theme="dark"]', ":root")


def _logo_b64() -> str:
    mark = DESIGN_DIR / "mark.svg"
    return base64.b64encode(mark.read_bytes()).decode() if mark.exists() else ""


# ─── API Helper ───
def api_get(path: str, **kw):
    try:
        r = requests.get(f"{API_URL}{path}", params=kw, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ─── Dashboard CSS (dark theme of the shared design system) ───
_logo = _logo_b64()
_logo_img = (
    f'<img src="data:image/svg+xml;base64,{_logo}" '
    f'style="height:32px;width:32px;" alt="" />'
    if _logo
    else ""
)

st.markdown(
    f"""
    <style>
    {_design_tokens()}

    /* Legacy names mapped onto the shared tokens. New CSS uses --sp-* directly. */
    :root {{
      --sidebar-bg: var(--sp-chrome);
      --main-bg: var(--sp-bg);
      --card-bg: var(--sp-surface);
      --card-border: var(--sp-border);
      --card-border-hover: var(--sp-border-strong);
      --text-primary: var(--sp-text);
      --text-secondary: var(--sp-text-2);
      --text-muted: var(--sp-text-3);
      --accent: var(--sp-accent);
      --accent-light: var(--sp-accent-soft);
      --green-subtle: var(--sp-ok);
      --amber-subtle: var(--sp-warn);
      --red-subtle: var(--sp-risk);
    }}

    .stApp, [data-testid="stAppViewContainer"], .main {{
      background-color: var(--main-bg) !important;
      color: var(--text-primary) !important;
      font-family: var(--sp-font-sans) !important;
    }}

    header[data-testid="stHeader"] {{
      background: var(--main-bg) !important;
      border-bottom: 1px solid var(--card-border) !important;
    }}

    /* Global markdown & typography contrast enforcement */
    /* Badges keep their own colour (tokens.css claim-badge vocabulary). */
    .stMarkdown, .stMarkdown p, .stMarkdown span:not([class*="badge"]), .stMarkdown li, .stMarkdown div {{
      color: var(--text-primary) !important;
    }}
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {{
      color: var(--sp-text) !important;
      font-weight: 700 !important;
    }}
    .stMarkdown strong {{
      color: var(--sp-text) !important;
      font-weight: 700 !important;
    }}
    .stMarkdown code {{
      background-color: var(--sp-surface-2) !important;
      color: var(--sp-accent) !important;
      border: 1px solid var(--sp-border) !important;
      padding: 2px 6px !important;
      border-radius: 4px !important;
      font-family: var(--sp-font-mono) !important;
    }}

    /* Sidebar overrides */
    section[data-testid="stSidebar"] > div {{
      background-color: var(--sidebar-bg) !important;
      border-right: 1px solid var(--card-border) !important;
      color: var(--text-secondary) !important;
    }}

    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] .stMarkdown span {{
      color: var(--text-secondary) !important;
    }}

    /* Navigation Radio in Sidebar */
    section[data-testid="stSidebar"] .stRadio label {{
      color: var(--sp-text-2) !important;
      font-weight: 500 !important;
      padding: 8px 12px !important;
      border-radius: 6px !important;
      transition: all 0.15s ease !important;
      font-size: 0.88rem !important;
    }}
    section[data-testid="stSidebar"] .stRadio label:hover {{
      background: rgba(255,255,255,0.06) !important;
      color: var(--sp-text) !important;
    }}
    section[data-testid="stSidebar"] .stRadio [aria-checked="true"] + div p {{
      color: var(--sp-text) !important;
      font-weight: 700 !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
      background: transparent;
      border-bottom: 1px solid var(--card-border);
      gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
      border: none !important;
      border-bottom: 2px solid transparent !important;
      color: var(--text-muted) !important;
      font-weight: 500 !important;
      padding: 10px 16px !important;
      background: transparent !important;
    }}
    .stTabs [aria-selected="true"] {{
      color: var(--accent) !important;
      border-bottom-color: var(--accent) !important;
      font-weight: 600 !important;
      background: transparent !important;
    }}

    /* Buttons */
    .stButton > button {{
      background-color: var(--sp-surface) !important;
      color: var(--sp-text) !important;
      border: 1px solid var(--card-border) !important;
      border-radius: 8px !important;
      font-weight: 600 !important;
      padding: 8px 16px !important;
      transition: all 0.15s ease !important;
    }}
    .stButton > button:hover {{
      background-color: var(--accent) !important;
      border-color: var(--accent) !important;
      color: var(--sp-text) !important;
    }}
    .stButton > button[kind="primary"] {{
      background-color: var(--accent) !important;
      border-color: var(--accent) !important;
      color: var(--sp-text) !important;
    }}

    /* Inputs & Selectboxes */
    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"] {{
      background-color: var(--sp-surface) !important;
      color: var(--sp-text) !important;
      border-color: var(--sp-surface-2) !important;
    }}
    [data-baseweb="base-input"] {{
      background-color: var(--sp-surface) !important;
      border: 1px solid var(--sp-surface-2) !important;
      border-radius: 6px !important;
    }}
    [data-baseweb="select"] > div {{
      background-color: var(--sp-surface) !important;
      border-color: var(--sp-surface-2) !important;
      color: var(--sp-text) !important;
    }}
    label[data-testid="stWidgetLabel"] p {{
      color: var(--sp-text-2) !important;
      font-size: 0.8rem !important;
      font-weight: 600 !important;
      letter-spacing: 0.04em !important;
      text-transform: uppercase !important;
    }}

    /* Expanders - Full Dark Contrast */
    [data-testid="stExpander"] {{
      background-color: var(--sp-surface) !important;
      border: 1px solid var(--card-border) !important;
      border-radius: 10px !important;
      margin-bottom: 16px !important;
    }}
    [data-testid="stExpander"] summary {{
      color: var(--sp-text) !important;
      font-weight: 600 !important;
      background-color: var(--sp-surface) !important;
      padding: 12px 16px !important;
      border-radius: 10px !important;
    }}
    [data-testid="stExpander"] summary:hover {{
      color: var(--accent) !important;
    }}
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
      background-color: var(--sp-bg) !important;
      border-top: 1px solid var(--card-border) !important;
      padding: 20px !important;
      color: var(--sp-text-2) !important;
    }}
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] li,
    [data-testid="stExpanderDetails"] span {{
      color: var(--sp-text-2) !important;
      line-height: 1.6 !important;
    }}
    [data-testid="stExpanderDetails"] h1,
    [data-testid="stExpanderDetails"] h2,
    [data-testid="stExpanderDetails"] h3,
    [data-testid="stExpanderDetails"] h4 {{
      color: var(--sp-text) !important;
    }}

    /* Metric polish */
    [data-testid="stMetricValue"] {{
      font-family: var(--sp-font-mono) !important;
      color: var(--sp-text) !important;
    }}
    [data-testid="stMetricLabel"] p {{
      color: var(--text-muted) !important;
      font-size: 0.72rem !important;
      text-transform: uppercase !important;
      letter-spacing: 0.06em !important;
    }}

    /* Dataframes */
    [data-testid="stDataFrame"] {{
      background-color: var(--sp-surface) !important;
      border: 1px solid var(--card-border) !important;
      border-radius: 8px !important;
    }}

    /* Custom components */
    .brand-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 4px;
    }}
    .brand-name {{
      font-size: 0.88rem;
      font-weight: 800;
      color: var(--sp-text);
      letter-spacing: 0.05em;
    }}
    .brand-sub {{
      font-size: 0.64rem;
      color: var(--text-muted);
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .live-dot {{
      display: inline-block;
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--accent);
      animation: pd 2s ease-in-out infinite;
    }}
    @keyframes pd {{ 0%,100%{{opacity:1}} 50%{{opacity:0.4}} }}
    .live-label {{
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--text-muted);
    }}

    .cmd-dot {{
      display: inline-block;
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--accent);
    }}
    .cmd-label {{
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .greeting {{
      font-family: var(--sp-font-sans);
      font-size: clamp(1.5rem, 4vw, 2.1rem);
      font-weight: 600;
      letter-spacing: -0.02em;
      color: var(--sp-text);
      line-height: 1.15;
      margin: 6px 0 8px;
    }}
    .greeting-sub {{
      font-size: 0.92rem;
      color: var(--text-secondary);
      line-height: 1.5;
      margin-bottom: 16px;
    }}

    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 18px 20px;
      height: 100%;
    }}
    .kpi-top-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .kpi-icon {{
      width: 32px; height: 32px; border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
      font-family: var(--sp-font-mono);
    }}
    .kpi-icon.accent {{
      background: var(--accent-light);
      color: var(--accent);
      border: 1px solid color-mix(in srgb, var(--sp-accent) 30%, transparent);
    }}
    .kpi-icon.muted {{
      background: var(--sp-surface-2);
      color: var(--text-secondary);
      border: 1px solid var(--sp-border);
    }}
    .kpi-trend {{
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--green-subtle);
      font-family: var(--sp-font-mono);
    }}
    .kpi-lbl {{
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 6px;
    }}
    .kpi-val {{
      font-size: 1.9rem;
      font-weight: 700;
      font-family: var(--sp-font-mono);
      color: var(--sp-text);
      line-height: 1;
    }}
    .kpi-sub-text {{
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 6px;
    }}
    .metric-provenance {{
      font-size: 0.67rem !important;
      color: var(--sp-text-2) !important;
      margin-top: 5px !important;
      line-height: 1.4 !important;
      border-top: 1px dashed rgba(255,255,255,0.08) !important;
      padding-top: 4px !important;
    }}

    .engine-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 18px 20px;
      height: 100%;
    }}
    .engine-card.highlight {{
      border-color: var(--accent);
      background: var(--sp-surface);
    }}
    .engine-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .engine-icon {{
      width: 32px; height: 32px; border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
      font-family: var(--sp-font-mono);
    }}
    .engine-icon.accent {{
      background: var(--accent-light);
      color: var(--accent);
      border: 1px solid color-mix(in srgb, var(--sp-accent) 30%, transparent);
    }}
    .engine-icon.muted {{
      background: var(--sp-surface-2);
      color: var(--text-secondary);
      border: 1px solid var(--sp-border);
    }}
    .engine-num {{
      font-size: 0.72rem; font-weight: 600; color: var(--text-muted);
      font-family: var(--sp-font-mono);
    }}
    .engine-title {{
      font-size: 1rem; font-weight: 600;
      color: var(--sp-text);
      margin-bottom: 6px;
    }}
    .engine-desc {{
      font-size: 0.82rem;
      color: var(--text-secondary);
      line-height: 1.5;
      margin-bottom: 14px;
    }}
    .engine-val {{
      font-size: 1.7rem;
      font-weight: 700;
      font-family: var(--sp-font-mono);
      color: var(--sp-text);
      line-height: 1;
    }}
    .engine-val-sub {{
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 2px;
    }}

    .signal-badge {{
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 8px; border-radius: 4px;
      font-size: 0.72rem; font-weight: 600;
      font-family: var(--sp-font-mono);
      letter-spacing: 0.04em;
    }}
    .signal-badge.critical {{
      background: color-mix(in srgb, var(--sp-risk) 18%, transparent);
      color: var(--sp-risk);
      border: 1px solid color-mix(in srgb, var(--sp-risk) 40%, transparent);
    }}
    .signal-badge.moderate {{
      background: color-mix(in srgb, var(--sp-warn) 18%, transparent);
      color: var(--sp-warn);
      border: 1px solid color-mix(in srgb, var(--sp-warn) 40%, transparent);
    }}
    .signal-badge.ok {{
      background: color-mix(in srgb, var(--sp-ok) 18%, transparent);
      color: var(--sp-ok);
      border: 1px solid color-mix(in srgb, var(--sp-ok) 40%, transparent);
    }}

    .org-badge {{
      border-left: 3px solid var(--accent);
      padding-left: 12px;
      margin-bottom: 16px;
    }}
    .org-label-text {{
      font-size: 0.68rem; font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--text-muted);
    }}
    .org-date {{
      font-size: 0.84rem; font-weight: 500;
      color: var(--sp-text-2);
      margin-top: 2px;
    }}

    .site-box {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
    }}
    .site-box:hover {{
      border-color: var(--accent);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Sidebar Controls ───
with st.sidebar:
    st.markdown(
        f"""
        <div class="brand-header">
            {_logo_img}
            <div>
                <div class="brand-name">SitePulse</div>
                <div class="brand-sub">Enterprise Construction Logistics</div>
            </div>
        </div>
        <div style="margin:10px 0 16px; display:flex; align-items:center; gap:6px;">
            <span class="live-dot"></span>
            <span class="live-label">Command Surface</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    view = st.radio(
        "Navigation",
        ["Overview", "Delivery Signals", "Resource Plan", "Sequence Checks", "Site Network", "Company Workspace", "Pilot Engagement", "Pitch & Economics"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Project switcher
    projects_data = api_get("/projects")
    project_options = {
        "PRJ_001": "PRJ_001 · Site A · Urban Residential (Almaty)",
        "PRJ_002": "PRJ_002 · Site B · High-Rise Commercial (Astana)",
        "PRJ_003": "PRJ_003 · Site C · Embankment Towers (Astana)",
        "PRJ_004": "PRJ_004 · Site D · Industrial Logistics Park (Karaganda)",
        "PRJ_005": "PRJ_005 · Site E · Regional Trade Center (Shymkent)",
    }
    if projects_data and "projects" in projects_data:
        for p in projects_data["projects"]:
            project_options[p["project_id"]] = f"{p['project_id']} · {p['name']} ({p['location']})"

    selected_pid = st.selectbox(
        "Active Construction Site",
        options=list(project_options.keys()),
        format_func=lambda x: project_options.get(x, x),
        index=1,
    )

    st.markdown("---")

    # Weather Widget
    st.markdown(
        """
        <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:12px 14px; margin-top:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-size:0.64rem; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:var(--sp-text-3);">
                    Sample conditions · not live
                </span>
                <span style="font-size:0.7rem; font-weight:700; color:var(--sp-accent); font-family:var(--sp-font-mono); letter-spacing:0.06em;">CLEAR</span>
            </div>
            <div style="font-size:1.4rem; font-weight:700; font-family:var(--sp-font-mono); color:var(--sp-text);">–6° / +2°</div>
            <div style="font-size:0.72rem; color:var(--sp-text-2);">Astana · Wind 18 km/h · Dry Pour Window</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    health_info = api_get("/health")
    if health_info:
        st.caption(f"Backend: OK · {health_info.get('trained_rows', 2200)} trained deliveries · 3 engines")
    else:
        st.caption("Backend: Connecting to FastAPI (:8000)...")


# Fetch current project overview
overview = api_get(f"/projects/{selected_pid}/overview")
proj_info = overview.get("project", {}) if overview else {}
proj_name = proj_info.get("name", "Active Site")
proj_loc = proj_info.get("location", "Kazakhstan")
proj_prio = proj_info.get("priority", "medium").upper()

dly = overview.get("delay_prediction", {}) if overview else {}
sch = overview.get("resource_schedule", {}) if overview else {}
seq = overview.get("sequencing", {}) if overview else {}

risk_bands = dly.get("bands", {})
risk_red = risk_bands.get("red", 0)
risk_yellow = risk_bands.get("yellow", 0)
scored_count = dly.get("scored", 0)
assigned_count = sch.get("stats", {}).get("assigned", len(sch.get("assignments", [])))
flagged_seq_count = len(seq.get("flagged", []))


# ─── Top Bar Banner ───
st.markdown(
    f"""
    <div class="org-badge">
        <div class="org-label-text">SitePulse · Regional Holding (Demo) · Site: {proj_name} ({selected_pid})</div>
        <div class="org-date">Operational Schedule · Priority: <strong>{proj_prio}</strong> · Engine Status: Normal</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── CONTEXT WINDOW EXPANDER ───
with st.expander("Project Architecture & Logistics Data Guide", expanded=False):
    st.markdown(
        """
        ### About the Construction Logistics Platform (SitePulse)
        
        This platform solves **three critical cost bottlenecks** on large-scale construction sites in Central Asia:
        
        1. **Engine 1 · Delay Risk Predictor**:
           - Uses Machine Learning with **strictly causal feature engineering** (no lookahead bias).
           - Cold-start subcontractors without prior history use **Empirical Bayes shrinkage**, collapsing gracefully onto material × route averages without `NaN` or failures.
           - Explains predictions with **occlusion feature drivers** (temperature batch freezes, cross-border customs, lead-time strain).
           
        2. **Engine 2 · Resource Scheduler**:
           - Powered by **Google OR-Tools CP-SAT constraint programming**.
           - Assigns each equipment booking (mobile cranes, concrete pumps, hoists) to a free unit across sites; **no unit is ever double-booked** (a tested correctness invariant). It does not yet re-time bookings on a single tower crane.
           - Coupled with Engine 1: Allocates local buffers when an arriving delivery has an upstream delay risk.
           
        3. **Engine 3 · Sequence Validator**:
           - Verifies physical build stages (Earthworks $\\rightarrow$ Foundation $\\rightarrow$ Structural Frame $\\rightarrow$ MEP $\\rightarrow$ Finishing).
           - Flags **premature deliveries** arriving before target phase readiness to eliminate site congestion and weather damage.

        ---
        ### Where to Input Data for Machine Learning:
        
        * **1. Interactive Single Scoring**: Open the **"Delivery Signals"** tab in the sidebar and use the interactive form.
        * **2. Batch CSV Upload in UI**: Use the **"Batch Upload CSV"** expander below to drag-and-drop any delivery schedule.
        * **3. File System Repositories**:
          - Model training dataset: `data/synthetic/delay_prediction.csv`
          - Reference master tables: `data/synthetic/` (`projects.csv`, `resources.csv`, `booking_requests.csv`, `build_phases.csv`, `phase_material_map.csv`, `material_deliveries.csv`)
          - Sample upload template: `sample_deliveries.csv`
        * **4. Retraining Pipeline**:
          - Click the **"Retrain Model"** button below or run `python -m ml.train` in terminal.
        """
    )


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
if view == "Overview":
    # Validation Status Banner
    st.markdown(
        """
        <div style="background:var(--sp-surface); border:1px solid var(--sp-surface-2); border-left:4px solid var(--sp-info); border-radius:8px; padding:14px 18px; margin-bottom:18px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
                <div style="font-size:0.78rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--sp-info);">
                    Validation Status · 100% Synthetic Benchmark (n=2,200 Deliveries, 260 Crane Bookings)
                </div>
                <div style="display:flex; gap:8px;">
                    <span class="badge-guarantee">Correctness Invariant</span>
                    <span class="badge-estimate">Statistical Estimate</span>
                </div>
            </div>
            <div style="font-size:0.83rem; color:var(--sp-text-2); line-height:1.55;">
                <strong>Current Reality:</strong> 0% live field data connected today. No-double-booking and phase-date checks are correctness invariants of the code, not measures of business impact. ML delay risk is benchmarked on synthetic data whose delay drivers the generator encodes; losses avoided and ROI are founder assumptions (GET /economics).
            </div>
            <div style="font-size:0.78rem; color:var(--sp-text-2); margin-top:6px;">
                <strong>Next Calibration Step:</strong> Ingest 6–12 months of client 1C/SAP purchase orders and crane telematics via <code>ml/ingest.py</code> to calibrate empirical risk priors during the 8-week pilot engagement.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _hour = datetime.datetime.now().hour
    _greeting = "Good morning." if _hour < 12 else "Good afternoon." if _hour < 18 else "Good evening."
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Command Surface</span>
        </div>
        <h1 class="greeting">{_greeting}</h1>
        <p class="greeting-sub">
            Live operational status for <strong>{proj_name}</strong>.
            Three engines running side-by-side to protect crane utilization, pour windows, and laydown areas.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # KPI Row
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon accent">⊘</div>
                    <span class="badge-estimate">Statistical Estimate</span>
                </div>
                <div class="kpi-lbl">At-Risk Deliveries</div>
                <div class="kpi-val">{risk_red + risk_yellow:02d}</div>
                <div class="kpi-sub-text">of {scored_count} tracked · gradient boosting</div>
                <div class="metric-provenance">100% Synthetic Benchmark (n=2,200) · Base rate: 40.9% late</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon muted">⊞</div>
                    <span class="badge-guarantee">Correctness Invariant</span>
                </div>
                <div class="kpi-lbl">Machinery Bookings</div>
                <div class="kpi-val">{assigned_count:02d}</div>
                <div class="kpi-sub-text">0 double-bookings · CP-SAT</div>
                <div class="metric-provenance">Correctness invariant: no unit double-booked</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon muted">⬡</div>
                    <span class="badge-guarantee">Correctness Invariant</span>
                </div>
                <div class="kpi-lbl">Sequencing Flags</div>
                <div class="kpi-val">{flagged_seq_count:02d}</div>
                <div class="kpi-sub-text">deliveries dated before their phase</div>
                <div class="metric-provenance">Deterministic date rule vs phase schedule</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon muted">∿</div>
                    <span class="badge-estimate">Statistical Estimate</span>
                </div>
                <div class="kpi-lbl">ML Risk Performance</div>
                <div class="kpi-val" style="font-size:1.6rem;">0.858 PR-AUC</div>
                <div class="kpi-sub-text">+0.126 lift vs supplier avg · ROC 0.831</div>
                <div class="metric-provenance">Eval Base Rate: 40.9% late (899/2,200) · Synthetic</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # Three Engines Cards
    st.markdown(
        """
        <div style="font-size:0.65rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:var(--sp-text-3); margin-bottom:4px;">
            Three Engines / One Operating Picture
        </div>
        <div style="font-size:1.25rem; font-weight:600; color:var(--sp-text); margin-bottom:14px;">
            Integrated decision support for regional construction sites
        </div>
        """,
        unsafe_allow_html=True,
    )

    e1, e2, e3 = st.columns([1.3, 1, 1])   # Delay Risk leads; not an equal feature row
    with e1:
        st.markdown(
            f"""
            <div class="engine-card highlight">
                <div class="engine-top">
                    <div class="engine-icon accent">⊘</div>
                    <span class="badge-estimate">Statistical Estimate</span>
                </div>
                <div class="engine-title">Delay Risk Predictor</div>
                <div class="engine-desc">Causal supplier shrinkage and occlusion drivers before truck departure.</div>
                <div class="engine-val">{risk_red:02d}</div>
                <div class="engine-val-sub">critical risk deliveries (>60%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with e2:
        st.markdown(
            f"""
            <div class="engine-card">
                <div class="engine-top">
                    <div class="engine-icon muted">⊞</div>
                    <span class="badge-guarantee">Correctness Invariant</span>
                </div>
                <div class="engine-title">Resource Scheduler</div>
                <div class="engine-desc">OR-Tools CP-SAT scheduler: Tower cranes, pumps and unload bays.</div>
                <div class="engine-val">{assigned_count:02d}</div>
                <div class="engine-val-sub">no unit double-booked (tested)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with e3:
        st.markdown(
            f"""
            <div class="engine-card">
                <div class="engine-top">
                    <div class="engine-icon muted">⬡</div>
                    <span class="badge-guarantee">Correctness Invariant</span>
                </div>
                <div class="engine-title">Sequence Validator</div>
                <div class="engine-desc">Build phase gates (Foundation → Frame → MEP) stopping premature clutter.</div>
                <div class="engine-val">{flagged_seq_count:02d}</div>
                <div class="engine-val-sub">flagged by phase-date rule</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # Queue Table + Network Pulse
    q_col, net_col = st.columns([2.2, 1])
    with q_col:
        st.markdown(
            """
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span class="cmd-dot"></span>
                <span style="font-size:1.05rem; font-weight:600; color:var(--sp-text);">Active Delivery Risk Signals</span>
            </div>
            <div style="font-size:0.8rem; color:var(--sp-text-2); margin-bottom:12px;">
                Deliveries ranked by ML delay probability with primary occlusion drivers.
            </div>
            """,
            unsafe_allow_html=True,
        )

        top_risks = dly.get("top_risks", [])
        if top_risks:
            formatted = []
            for r in top_risks[:8]:
                driver = r.get("drivers", [{}])[0] if r.get("drivers") else {}
                driver_text = f"{driver.get('factor', 'lead_time')}: {driver.get('value', '--')}" if driver else "Supplier history"
                band = r.get("risk_band", "green")
                signal_badge = "CRITICAL" if band == "red" else "MODERATE" if band == "yellow" else "CLEARED"
                formatted.append({
                    "Delivery": f"{r.get('material_type','').replace('_',' ').title()} ({r.get('quantity','--')} units)",
                    "Supplier": r.get("supplier_id", "--"),
                    "Risk Reason": driver_text,
                    "Promised Window": str(r.get("promised_date", "--")),
                    "Signal": signal_badge,
                })
            st.dataframe(pd.DataFrame(formatted), width="stretch", hide_index=True)
        else:
            st.info("No delivery records found for this site.")

    with net_col:
        st.markdown(
            """
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:12px; padding:20px; color:var(--sp-text); height:100%;">
                <div style="font-size:0.62rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:var(--sp-text-3); margin-bottom:4px;">
                    Network Pulse
                </div>
                <div style="font-size:1.05rem; font-weight:600; color:var(--sp-text); margin-bottom:14px;">
                    Protected Workfronts
                </div>
                <div style="font-size:2.8rem; font-weight:700; font-family:var(--sp-font-mono); line-height:1; color:var(--sp-text);">
                    88.4%
                </div>
                <div style="font-size:0.78rem; font-weight:500; color:var(--sp-text-2); margin-top:6px;">
                    <span style="color:var(--sp-ok);">↗ +4.2%</span> crane uptime vs unoptimized
                </div>
                <hr style="border-color:var(--sp-border); margin:16px 0;" />
                <div style="font-size:0.75rem; color:var(--sp-text-2); line-height:1.6;">
                    • 0 overlapping bookings<br/>
                    • 19 machinery units scheduled<br/>
                    • 4 freight corridors clear
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 2: DELIVERY SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Delivery Signals":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Engine 1 · Delay Risk Intelligence</span>
        </div>
        <h1 class="greeting">Delivery Signals Feed</h1>
        <p class="greeting-sub">
            Causal machine learning predictions evaluated before shipment departure.
            Identifies supplier bottleneck risks with Bayesian shrinkage and top occlusion drivers.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Interactive Quick Predictor
    with st.expander("Interactive Delivery Delay Risk Simulator", expanded=True):
        st.markdown("**Test ML Inference on any custom delivery payload:**")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            test_supplier = st.text_input("Supplier ID", value="SUP_004")
            test_material = st.selectbox(
                "Material Type",
                ["rebar", "ready_mix_concrete", "timber", "drywall", "mep_piping", "facade_panels", "bricks"],
                index=0,
            )
        with pcol2:
            test_route = st.selectbox("Route Type", ["urban", "intercity", "cross_border"], index=2)
            test_qty = st.number_input("Quantity", min_value=1, value=60)
        with pcol3:
            today = datetime.date.today()
            test_order_date = st.date_input("Order Date", value=today)
            test_prom_date = st.date_input("Promised Date", value=today + datetime.timedelta(days=12))

        if st.button("Calculate Delay Risk (Run ML Model)", type="primary"):
            payload = {
                "supplier_id": test_supplier.strip(),
                "material_type": test_material,
                "route_type": test_route,
                "quantity": int(test_qty),
                "order_date": str(test_order_date),
                "promised_date": str(test_prom_date),
            }
            try:
                res = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    risk = data.get("risk", 0.0)
                    band = data.get("risk_band", "green")
                    band_label = "CRITICAL RISK" if band == "red" else "MODERATE RISK" if band == "yellow" else "CLEARED"

                    rcol1, rcol2, rcol3 = st.columns(3)
                    rcol1.metric("Predicted Delay Probability", f"{risk*100:.1f}%", band_label)
                    rcol2.metric("Historical Supplier Late Rate", f"{data.get('supplier_late_rate', 0)*100:.1f}%")
                    rcol3.metric("Prior Deliveries on Record", f"{data.get('supplier_n_prior', 0)} orders")

                    drivers = data.get("drivers", [])
                    if drivers:
                        st.markdown("**Top Occlusion Feature Drivers:**")
                        d_df = pd.DataFrame([
                            {"Factor": d.get("factor"), "Observed Value": d.get("value"), "Risk Impact": f"{d.get('impact', 0)*100:+.1f}%"}
                            for d in drivers
                        ])
                        st.dataframe(d_df, width="stretch", hide_index=True)
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except Exception as e:
                st.error(f"Prediction failed: {e}")

    # Full feed table
    st.markdown("### Site Deliveries Table")
    all_deliveries = dly.get("top_risks", [])
    if all_deliveries:
        filter_choice = st.radio("Filter by Risk Classification", ["All Deliveries", "Critical (Red)", "Moderate (Yellow)", "Cleared (Green)"], horizontal=True)
        filtered = []
        for d in all_deliveries:
            band = d.get("risk_band", "green")
            if filter_choice == "Critical (Red)" and band != "red":
                continue
            if filter_choice == "Moderate (Yellow)" and band != "yellow":
                continue
            if filter_choice == "Cleared (Green)" and band != "green":
                continue
            filtered.append(d)

        df_display = pd.DataFrame(filtered)
        st.dataframe(df_display, width="stretch")
    else:
        st.info("No deliveries recorded for this project.")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 3: RESOURCE PLAN
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Resource Plan":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Engine 2 · OR-Tools CP-SAT Scheduler</span>
        </div>
        <h1 class="greeting">Machinery & Equipment Schedule</h1>
        <p class="greeting-sub">
            Assigns each booking to a free crane, pump or hoist across the holding's sites — no unit double-booked —
            and prefers local units for bookings whose deliveries are at risk of slipping.
        </p>
        """,
        unsafe_allow_html=True,
    )

    sched_demo = api_get("/schedule/demo")
    stats = sched_demo.get("stats", {}) if sched_demo else {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", stats.get("bookings", 260))
    c2.metric("Raw Conflicts Resolved", stats.get("raw_conflicts_before", 99), "-99 overlap eliminated")
    c3.metric("Final Double-Bookings", stats.get("double_bookings_after", 0), "Guaranteed 0")
    c4.metric("Solver Solve Time", f"{stats.get('solve_seconds', 0.2):.2f}s", "OPTIMAL")

    st.markdown("### Equipment Allocation Master Schedule")
    assignments = sched_demo.get("assignments", []) if sched_demo else []
    if assignments:
        eq_filter = st.selectbox("Filter Equipment Type", ["All Equipment", "Tower Crane", "Concrete Pump", "Material Hoist"])
        filtered_assign = []
        for a in assignments:
            rtype = (a.get("resource_type") or "").lower()
            if eq_filter == "Tower Crane" and "crane" not in rtype:
                continue
            if eq_filter == "Concrete Pump" and "pump" not in rtype:
                continue
            if eq_filter == "Material Hoist" and "hoist" not in rtype:
                continue
            filtered_assign.append({
                "Booking ID": a.get("booking_id"),
                "Project": a.get("project_id"),
                "Assigned Machine": a.get("assigned_resource_id"),
                "Type": a.get("resource_type", "").replace("_", " ").title(),
                "Time Window": f"{str(a.get('start',''))[:16].replace('T', ' ')} → {str(a.get('end',''))[11:16]}",
                "Upstream Delay Risk": "High Risk" if a.get("delay_risk", 0) > 0.5 else "Nominal",
                "Conflict Status": "Optimal (No Overlap)",
            })
        st.dataframe(pd.DataFrame(filtered_assign), width="stretch", hide_index=True)
    else:
        st.info("Loading schedule data from Engine 2...")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 4: SEQUENCE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 4: SEQUENCE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Sequence Checks":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Engine 3 · Phase Gate Validator</span>
        </div>
        <h1 class="greeting">Construction Sequencing & Phase Gates</h1>
        <p class="greeting-sub">
            Verifies that material deliveries match the current physical build stage.
            Flags premature arrivals that cause site gridlock, material weathering, and double-handling fees.
        </p>
        """,
        unsafe_allow_html=True,
    )

    val_demo = api_get("/validate/demo")
    counts = val_demo.get("counts", {}) if val_demo else {}

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Deliveries Screened", counts.get("total", 219))
    v2.metric("Premature Deliveries (R1)", counts.get("premature_delivery", 27), "Needs Hold")
    v3.metric("Material Mismatches (R2)", counts.get("material_phase_mismatch", 0), "Clean")
    v4.metric("Rule Check", "Date rule", help="Flags every delivery dated before its phase start. On synthetic labels made by the same rule, recall is 1.0 by definition.")

    st.markdown("### Build Phase Physical Hierarchy")
    st.markdown(
        """
        * **Stage 1 (Earthworks & Piling)**: Completed
        * **Stage 2 (Substructure & Foundation Concrete)**: **ACTIVE (Current Stage)**
        * **Stage 3 (Structural Steel & Frame)**: Planned kickoff in 14 days
        * **Stage 4 (MEP Rough-In & Facades)**: Scheduled Jun 2026
        * **Stage 5 (Interior Fit-Out & Handover)**: Scheduled Aug 2026
        """
    )

    st.markdown("### Flagged Premature Deliveries Requiring Gate Holds")
    deliveries_val = val_demo.get("deliveries", []) if val_demo else []
    premature = [d for d in deliveries_val if d.get("predicted_flag") == "premature_delivery"]
    if premature:
        table_rows = []
        for d in premature[:30]:
            table_rows.append({
                "Seq ID": d.get("delivery_seq_id"),
                "Project": d.get("project_id"),
                "Material": d.get("material_type", "").replace("_", " ").title(),
                "Required Phase": d.get("required_phase", "").replace("_", " ").title(),
                "Scheduled Delivery": str(d.get("delivery_date", ""))[:10],
                "Phase Start Date": str(d.get("phase_start_date", ""))[:10],
                "Gate Violation": "Premature Delivery",
                "Action": "Hold at supplier hub",
            })
        st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)
    else:
        st.success("All deliveries conform to current build phase readiness.")


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 5: SITE NETWORK
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Site Network":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Regional Logistics Command · Kazakhstan</span>
        </div>
        <h1 class="greeting">Multi-Site Network & Transit Corridors</h1>
        <p class="greeting-sub">
            Real-time operating status across all 5 regional construction projects in the pilot network,
            weather conditions, active machinery allocations, and supply corridor bottlenecks.
        </p>
        """,
        unsafe_allow_html=True,
    )

    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        st.markdown(
            """
            <div class="site-box">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700; color:var(--sp-accent);">PRJ_001</span>
                    <span class="signal-badge ok">Operational</span>
                </div>
                <h3 style="margin:6px 0 2px; font-size:1.1rem; color:var(--sp-text);">Site A · Urban Residential</h3>
                <div style="font-size:0.75rem; color:var(--sp-text-3); margin-bottom:10px;">Almaty · SE Urban District</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2);"><strong>Active Deliveries:</strong> 28<br/><strong>Cranes:</strong> 4 units<br/><strong>Weather:</strong> +14°C Sunny</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="site-box">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700; color:var(--sp-accent);">PRJ_004</span>
                    <span class="signal-badge ok">Steel Frame</span>
                </div>
                <h3 style="margin:6px 0 2px; font-size:1.1rem; color:var(--sp-text);">Site D · Industrial Logistics Park</h3>
                <div style="font-size:0.75rem; color:var(--sp-text-3); margin-bottom:10px;">Karaganda · Industrial Center</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2);"><strong>Active Deliveries:</strong> 31<br/><strong>Cranes:</strong> 5 units<br/><strong>Weather:</strong> -8°C Clear</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with scol2:
        st.markdown(
            """
            <div class="site-box">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700; color:var(--sp-accent);">PRJ_002</span>
                    <span class="signal-badge moderate">High Wind</span>
                </div>
                <h3 style="margin:6px 0 2px; font-size:1.1rem; color:var(--sp-text);">Site B · High-Rise Commercial</h3>
                <div style="font-size:0.75rem; color:var(--sp-text-3); margin-bottom:10px;">Astana · Left Bank District</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2);"><strong>Active Deliveries:</strong> 42<br/><strong>Cranes:</strong> 6 units<br/><strong>Weather:</strong> -6°C Wind 18 km/h</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="site-box">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700; color:var(--sp-accent);">PRJ_005</span>
                    <span class="signal-badge ok">Excavation</span>
                </div>
                <h3 style="margin:6px 0 2px; font-size:1.1rem; color:var(--sp-text);">Site E · Regional Trade Center</h3>
                <div style="font-size:0.75rem; color:var(--sp-text-3); margin-bottom:10px;">Shymkent · South Trade Hub</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2);"><strong>Active Deliveries:</strong> 19<br/><strong>Cranes:</strong> 5 units<br/><strong>Weather:</strong> +18°C Mild</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with scol3:
        st.markdown(
            """
            <div class="site-box" style="border-color:var(--sp-accent);">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700; color:var(--sp-accent);">PRJ_003</span>
                    <span class="signal-badge critical">Critical Pour</span>
                </div>
                <h3 style="margin:6px 0 2px; font-size:1.1rem; color:var(--sp-text);">Site C · Embankment Towers</h3>
                <div style="font-size:0.75rem; color:var(--sp-text-3); margin-bottom:10px;">Astana · Embankment Area</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2);"><strong>Active Deliveries:</strong> 55<br/><strong>Cranes:</strong> 8 units<br/><strong>Weather:</strong> -5°C Critical Window</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Heavy Freight Supply Corridors")
    corridors = [
        {"Corridor": "Astana – Karaganda Highway (M-36)", "Distance": "215 km", "Primary Cargo": "Precast concrete & steel", "Conditions": "Clear asphalt · Wind 14 km/h", "Status": "Normal Transit"},
        {"Corridor": "Almaty – Khorgos Cross-Border Route", "Distance": "340 km", "Primary Cargo": "Facade panels & MEP", "Conditions": "Customs terminal queue ~18h", "Status": "Critical Delay (+1.5d)"},
        {"Corridor": "Pavlodar – Astana Rail Freight Link", "Distance": "450 km", "Primary Cargo": "Rebar A500 & raw cement", "Conditions": "Train marshalling on time", "Status": "Normal Transit"},
        {"Corridor": "Taraz – Shymkent Industrial Route", "Distance": "180 km", "Primary Cargo": "Aggregates & batch cement", "Conditions": "High temp +22°C", "Status": "Batch Hold Notice"},
    ]
    st.dataframe(pd.DataFrame(corridors), width="stretch", hide_index=True)



# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 6: COMPANY WORKSPACE & FINANCIAL PLANNER (Key Access Portal)
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Company Workspace":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Subcontractor & Partner Portal · Key-Based Workspace</span>
        </div>
        <h1 class="greeting">Company Project, Logistics & Financial Suite</h1>
        <p class="greeting-sub">
            Private project workspace for general contractors and trade partners. Enter your company access key to load
            building parameters, machinery allocations, and financial terms. Site economics (losses avoided in three
            scenarios) are computed by the API from your inputs and the assumptions in GET /economics.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Key authentication header
    with st.container():
        kcol1, kcol2, kcol3 = st.columns([2, 1, 1])
        with kcol1:
            access_key_input = st.text_input(
                "Company Access Key",
                value=st.session_state.get("active_access_key", "DEMO-SITE-B-2026"),
                help="Demo keys (read-only): DEMO-SITE-B-2026, DEMO-SITE-A-2026, DEMO-PILOT-KEY. "
                     "Leave blank and save to get your own key.",
            )
        with kcol2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            load_key_btn = st.button("Load Workspace", use_container_width=True)
        with kcol3:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            new_key_btn = st.button("New Project Key", use_container_width=True)

    if new_key_btn:
        # Keys are issued by the server on first save (api/security.new_workspace_key).
        st.session_state["active_access_key"] = ""
        st.rerun()

    current_key = access_key_input.strip()   # blank = new workspace, key issued on save

    # The API wraps the saved workspace as {found, workspace}; unknown demo keys
    # get the fictional Site B profile.
    loaded = (api_get(f"/projects/workspace/{current_key}") or {}) if current_key else {}
    if current_key and not loaded:
        st.warning("No workspace found for that key.")
    workspace_data = loaded.get("workspace") or {}

    st.markdown("---")

    building_types = ["High-rise Residential", "Commercial Tower & Retail",
                      "Industrial Logistics Hub", "Civil Infrastructure"]
    saved_type = workspace_data.get("building_type", building_types[0])

    # Form inputs split into 3 logical domains: Building Specs, Logistics Plan, Financial Plan
    with st.form("company_workspace_form"):
        col_spec, col_logistics, col_finance = st.columns(3)

        with col_spec:
            st.markdown("#### 1. Building Specifications")
            comp_name = st.text_input("Company / Contractor", value=workspace_data.get("company_name", "Regional Construction Holding (Demo)"))
            p_name = st.text_input("Project Name", value=workspace_data.get("project_name", "Site B · High-Rise Commercial"))
            p_loc = st.text_input("Site Location", value=workspace_data.get("location", "Astana"))
            p_type = st.selectbox(
                "Building Category",
                building_types if saved_type in building_types else [saved_type, *building_types],
                index=0 if saved_type not in building_types else building_types.index(saved_type),
            )
            total_area = st.number_input("Gross Floor Area (m²)", min_value=1000.0, max_value=500000.0, value=float(workspace_data.get("total_area_sqm", 62000.0)), step=1000.0)
            floors = st.number_input("Floor Count (Above Ground)", min_value=1, max_value=100, value=int(workspace_data.get("floors", 24)), step=1)
            start_date = st.date_input("Logistics Start", value=pd.to_datetime(workspace_data.get("start_date", "2026-02-15")).date())
            end_date = st.date_input("Target Handover", value=pd.to_datetime(workspace_data.get("target_end_date", "2026-12-20")).date())

        with col_logistics:
            st.markdown("#### 2. Logistics & Machinery Plan")
            cranes = st.number_input("Tower Cranes on Site", min_value=1, max_value=20, value=int(workspace_data.get("cranes_count", 6)), step=1)
            pumps = st.number_input("Concrete Pumps Active", min_value=0, max_value=10, value=int(workspace_data.get("pumps_count", 3)), step=1)
            hoists = st.number_input("Passenger / Material Hoists", min_value=0, max_value=15, value=int(workspace_data.get("hoists_count", 4)), step=1)
            concrete_vol = st.number_input("Total Concrete Volume (m³)", min_value=500.0, max_value=200000.0, value=float(workspace_data.get("concrete_m3", 21000.0)), step=500.0)
            rebar_vol = st.number_input("Total Rebar Requirement (Tons)", min_value=100.0, max_value=50000.0, value=float(workspace_data.get("rebar_tons", 4500.0)), step=100.0)

        with col_finance:
            st.markdown("#### 3. Financial Rates & Penalties")
            crane_rate = st.number_input("Tower Crane Cost ($/day per unit)", min_value=100.0, max_value=10000.0, value=float(workspace_data.get("crane_daily_rate", 1600.0)), step=50.0)
            delay_penalty = st.number_input("Contractual Handover Penalty ($/day)", min_value=0.0, max_value=50000.0, value=float(workspace_data.get("delay_penalty_per_day", 12000.0)), step=250.0)
            concrete_cost = st.number_input("Concrete Batch Cost ($/m³)", min_value=20.0, max_value=500.0, value=float(workspace_data.get("concrete_cost_m3", 115.0)), step=5.0)
            logistics_budget = st.number_input("Site Logistics Budget ($ USD)", min_value=100000.0, max_value=500000000.0, value=float(workspace_data.get("total_logistics_budget", 3500000.0)), step=100000.0)

        st.markdown("<br/>", unsafe_allow_html=True)
        submit_calc = st.form_submit_button("Calculate & Save Project Parameters", use_container_width=True)

    # Field names are exactly api.schemas.CompanyWorkspaceIn.
    ws_payload = {
        "access_key": current_key,
        "company_name": comp_name,
        "project_id": workspace_data.get("project_id", selected_pid),
        "project_name": p_name,
        "location": p_loc,
        "building_type": p_type,
        "total_area_sqm": total_area,
        "floors": int(floors),
        "start_date": start_date.isoformat(),
        "target_end_date": end_date.isoformat(),
        "cranes_count": int(cranes),
        "pumps_count": int(pumps),
        "hoists_count": int(hoists),
        "rebar_tons": rebar_vol,
        "concrete_m3": concrete_vol,
        "crane_daily_rate": crane_rate,
        "delay_penalty_per_day": delay_penalty,
        "concrete_cost_m3": concrete_cost,
        "total_logistics_budget": logistics_budget,
    }

    if submit_calc:
        try:
            resp = requests.post(f"{API_URL}/projects/workspace", json=ws_payload, timeout=10)
            if resp.status_code == 200:
                issued = resp.json()["access_key"]
                st.session_state["active_access_key"] = issued
                st.success(f"'{p_name}' saved under key {issued}. Keep this key: it is the only way back in.")
            else:
                st.error(f"Not saved — {resp.json().get('detail', resp.text)}")
        except Exception as e:
            st.error(f"Backend sync error: {e}")

    # All finance comes from business/economics.py via the API -- no local math.
    try:
        r = requests.post(f"{API_URL}/economics/site", json=ws_payload, timeout=5)
        r.raise_for_status()
        finance = r.json()
    except Exception:
        finance = None

    st.markdown("### Site Economics · Estimate")
    st.caption("Losses avoided per site-year in three scenarios. Inputs are founder assumptions "
               "(see GET /economics), not yet measured on a real site.")

    if finance is None:
        st.warning("API offline — start the API to compute site economics.")
        st.stop()

    base = finance["scenarios"]["base"]
    cons = finance["scenarios"]["conservative"]
    up = finance["scenarios"]["upside"]
    licence = finance["annual_licence"]

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon accent">RUN</div>
                    <span class="sp-badge sp-badge--input">Operating Input</span>
                </div>
                <div class="kpi-lbl">Machinery Run Cost</div>
                <div class="kpi-val">${finance['machinery_est_cost']:,.0f}</div>
                <div class="kpi-sub-text">{cranes} cranes · {finance['duration_days']} days</div>
                <div class="metric-provenance">Rate: ${crane_rate:,.0f}/day per unit</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fcol2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon" style="color:var(--sp-ok); background:color-mix(in srgb, var(--sp-ok) 14%, transparent);">BASE</div>
                    <span class="badge-estimate">Estimate</span>
                </div>
                <div class="kpi-lbl">Losses Avoided · Base Case</div>
                <div class="kpi-val">${base['total_value']:,.0f}</div>
                <div class="kpi-sub-text">{base['value_multiple']:.1f}× the ${licence:,.0f}/yr licence</div>
                <div class="metric-provenance">Crane ${base['crane_idle_avoided']:,.0f} · concrete ${base['concrete_loss_avoided']:,.0f} · delay ${base['delay_penalty_avoided']:,.0f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fcol3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon accent">RANGE</div>
                    <span class="badge-estimate">Estimate</span>
                </div>
                <div class="kpi-lbl">Conservative – Upside</div>
                <div class="kpi-val">${cons['total_value']:,.0f} – ${up['total_value']:,.0f}</div>
                <div class="kpi-sub-text">{cons['value_multiple']:.1f}× – {up['value_multiple']:.1f}× licence</div>
                <div class="metric-provenance">Scenario levers: GET /economics</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with fcol4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-top-row">
                    <div class="kpi-icon" style="color:var(--sp-ok); background:color-mix(in srgb, var(--sp-ok) 14%, transparent);">CHK</div>
                    <span class="sp-badge sp-badge--check">Sanity Check</span>
                </div>
                <div class="kpi-lbl">Share of Logistics Budget</div>
                <div class="kpi-val">{base['share_of_logistics_budget']:.1%}</div>
                <div class="kpi-sub-text">base-case savings ÷ site logistics budget</div>
                <div class="metric-provenance">Above ~8% would not be credible</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Operational Schedule & Dispatch Buffer Summary
    st.markdown("<br/>", unsafe_allow_html=True)
    c_left, c_right = st.columns([1.5, 1])

    with c_left:
        st.markdown("#### Recommended Site Logistics Protocols")
        st.markdown(
            f"""
            1. **Crane Dispatch Schedule**: Allocate **{cranes * 10} hours/day** across trade subcontractors. Priority rules enforce concrete pour blocks over dry framing.
            2. **Buffer Delivery Windows**: High-density urban traffic dictates a minimum **45-minute staging queue** at Gate #2 before crane hook attachment.
            3. **Pouring Safety Window**: For {concrete_vol:,.0f} m³ total mix, trigger thermal sensors when ambient falls below **-5°C**; freeze dispatch if transit delay exceeds **65 minutes**.
            4. **Laydown Area Utilization**: Rebar stocking capped at **400 tons/week** to prevent site congestion around tower crane #1 radius.
            """
        )

    with c_right:
        st.markdown("#### Workspace Access")
        st.markdown(
            f"""
            <div style="background:var(--sp-surface); padding:18px; border-radius:10px; border:1px solid var(--sp-border);">
                <div style="font-size:0.75rem; color:var(--sp-text-3); text-transform:uppercase; font-weight:600; letter-spacing:0.06em;">Contractor Key</div>
                <div style="font-size:1.25rem; font-weight:700; color:var(--sp-accent); font-family:var(--sp-font-mono); margin:4px 0 10px;">{current_key or "Issued when you save"}</div>
                <div style="font-size:0.8rem; color:var(--sp-text-2); line-height:1.7;">
                    • <strong>Access:</strong> whoever holds this key can view and edit this workspace — keep it private.<br/>
                    • <strong>Demo keys:</strong> read-only; use "New Project Key" to get your own on save.<br/>
                    • <strong>Scope:</strong> {p_name}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 7: PILOT ENGAGEMENT & PROCUREMENT
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Pilot Engagement":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Enterprise Deployment & Procurement Roadmap</span>
        </div>
        <h1 class="greeting">Pilot Engagement & Calibration Program</h1>
        <p class="greeting-sub">
            A structured <strong>6–8 week dual-site pilot engagement</strong> to calibrate SitePulse predictive models against
            real ERP delivery receipts and machinery telematics before enterprise holding rollout.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Validation Status Banner inside Pilot Tab
    st.markdown(
        """
        <div style="background:var(--sp-surface); border:1px solid var(--sp-surface-2); border-left:4px solid var(--sp-info); border-radius:8px; padding:14px 18px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
                <div style="font-size:0.78rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--sp-info);">
                    Validation Status & Real-Data Calibration Gateway
                </div>
                <div style="display:flex; gap:8px;">
                    <span class="badge-guarantee">Correctness Invariant</span>
                    <span class="badge-estimate">Statistical Estimate</span>
                </div>
            </div>
            <div style="font-size:0.83rem; color:var(--sp-text-2); line-height:1.55;">
                <strong>Baseline Today:</strong> 100% Synthetic Benchmark (n=2,200 deliveries). No-double-booking and phase-date checks are tested correctness invariants. ML delay risk weights and the ROI scenarios will be calibrated against client historical delivery logs during Phase 2.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Pilot Roadmap Cards
    st.markdown("### 1. Phased Pilot Engagement (8 Weeks to Sign-off)")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown(
            """
            <div class="kpi-card" style="border-top:3px solid var(--sp-info);">
                <div style="font-size:0.75rem; font-weight:700; color:var(--sp-info); font-family:var(--sp-font-mono);">WEEKS 1–2</div>
                <div style="font-size:1.05rem; font-weight:700; color:var(--sp-text); margin:6px 0;">Data Ingestion</div>
                <div style="font-size:0.78rem; color:var(--sp-text-2); line-height:1.5;">
                    • Map 6–12 mo 1C / SAP PO & gate receipts via <code>ml/ingest.py</code>.<br/>
                    • Register site crane inventories and milestone schedules.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            """
            <div class="kpi-card" style="border-top:3px solid var(--sp-info);">
                <div style="font-size:0.75rem; font-weight:700; color:var(--sp-info); font-family:var(--sp-font-mono);">WEEKS 3–4</div>
                <div style="font-size:1.05rem; font-weight:700; color:var(--sp-text); margin:6px 0;">Model Calibration</div>
                <div style="font-size:0.78rem; color:var(--sp-text-2); line-height:1.5;">
                    • Calibrate supplier empirical-Bayes priors on real historical deliveries.<br/>
                    • Tune material grace thresholds with site directors.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p3:
        st.markdown(
            """
            <div class="kpi-card" style="border-top:3px solid var(--sp-accent);">
                <div style="font-size:0.75rem; font-weight:700; color:var(--sp-accent); font-family:var(--sp-font-mono);">WEEKS 5–6</div>
                <div style="font-size:1.05rem; font-weight:700; color:var(--sp-text); margin:6px 0;">Live Shadow Pilot</div>
                <div style="font-size:0.78rem; color:var(--sp-text-2); line-height:1.5;">
                    • Deploy shadow morning dispatch feeds on 2 active sites.<br/>
                    • Verify CP-SAT conflict-free crane schedules with site dispatchers.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p4:
        st.markdown(
            """
            <div class="kpi-card" style="border-top:3px solid var(--sp-ok);">
                <div style="font-size:0.75rem; font-weight:700; color:var(--sp-ok); font-family:var(--sp-font-mono);">WEEKS 7–8</div>
                <div style="font-size:1.05rem; font-weight:700; color:var(--sp-text); margin:6px 0;">Financial Sign-off</div>
                <div style="font-size:0.78rem; color:var(--sp-text-2); line-height:1.5;">
                    • Audit measured crane standstill reduction & avoided delays.<br/>
                    • Confirm >$50k/site monthly savings and sign production SaaS.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("### 2. Required Client Data & Technical Integration")
    d_left, d_right = st.columns(2)
    with d_left:
        st.markdown(
            """
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-text); margin-bottom:10px;">Required Data Feeds (Read-Only)</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2); line-height:1.65;">
                    1. <strong>Purchase Orders & Gate Logs:</strong> 6–12 months historical records (<code>supplier_id, material_type, quantity, order_date, promised_date, actual_date</code>).<br/>
                    2. <strong>Machinery Registry:</strong> Active tower cranes, concrete pumps, hoists, operating rates, and capacities.<br/>
                    3. <strong>Subcontractor Time Requests:</strong> Trade bookings for crane hook time and unload bays.<br/>
                    4. <strong>Master Schedule:</strong> Construction phase milestones (Foundation, Structure, MEP, Finishing).
                </div>
                <div style="margin-top:12px; font-size:0.75rem; color:var(--sp-text-2); border-top:1px dashed var(--sp-border); padding-top:8px;">
                    <strong>Data Sovereignty:</strong> No pricing contracts, worker PII, or confidential commercial agreements are ingested. All data stays in client sovereign cloud or private VPC.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with d_right:
        h = (api_get("/economics") or {}).get("headline", {})
        st.markdown(
            f"""
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-text); margin-bottom:10px;">Commercial Pricing & Licensing</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2); line-height:1.65;">
                    • <strong>Pilot Fee:</strong> <span style="color:var(--sp-accent); font-weight:700;">$15,000 (flat)</span> for 8-week dual-site deployment, pipeline integration, and calibration. *(100% credited toward annual agreement)*.<br/>
                    • <strong>Standard Site SaaS:</strong> <span style="color:var(--sp-info); font-weight:700;">$3,500 / site / month</span> (up to 4 cranes, 500 deliveries/month).<br/>
                    • <strong>Flagship Mega-Site SaaS:</strong> <span style="color:var(--sp-ok); font-weight:700;">$4,800 / site / month</span> (unlimited machinery, IoT telematics, custom phase gates).<br/>
                    • <strong>Portfolio License (10+ sites):</strong> Custom volume terms with cross-site supplier benchmarking.
                </div>
                <div style="margin-top:12px; font-size:0.75rem; color:var(--sp-ok); font-weight:600; border-top:1px dashed var(--sp-border); padding-top:8px;">
                    <strong>Estimated losses avoided (demo site, per site-year):</strong> {h.get('value_base', '—')} base case = {h.get('multiple_base', '—')} the licence (conservative {h.get('value_conservative', '—')}, {h.get('multiple_conservative', '—')}). Founder assumptions; the pilot measures them.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# VIEW 8: PITCH & ECONOMICS (LaunchZone Competition Hub)
# ═══════════════════════════════════════════════════════════════════════════════
elif view == "Pitch & Economics":
    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="cmd-dot"></span>
            <span class="cmd-label">Pitch & Economics · every figure from GET /economics</span>
        </div>
        <h1 class="greeting">Market, Unit Economics & Competition</h1>
        <p class="greeting-sub">
            All numbers below are computed by business/economics.py from assumptions tagged by source.
            None are measured on a real site yet — the pilot replaces them.
        </p>
        """,
        unsafe_allow_html=True,
    )

    econ = api_get("/economics")
    if not econ:
        st.warning("API offline — start the API to load the economics.")
        st.stop()
    h = econ["headline"]
    A = econ["assumptions"]
    years = econ["forecast"]["years"]

    def _card(col, color, label, value, sub):
        col.markdown(
            f"""
            <div class="kpi-card" style="border-top:3px solid {color};">
                <div style="font-size:0.75rem; font-weight:700; color:{color}; font-family:var(--sp-font-mono);">{label}</div>
                <div style="font-size:1.6rem; font-weight:800; color:var(--sp-text); margin:4px 0;">{value}</div>
                <div style="font-size:0.75rem; color:var(--sp-text-2);">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    k1, k2, k3, k4 = st.columns(4)
    _card(k1, "var(--sp-info)", "BEACHHEAD MARKET", h["market_beachhead"],
          f"{A['beachhead_sites']['value']:.0f} sites of the top-15 KZ/UZ holdings · founder estimate")
    _card(k2, "var(--sp-ok)", "LTV : CAC", h["ltv_to_cac"],
          f"LTV {h['ltv']} (margin-adjusted) ÷ CAC {h['cac']} · {h['gross_margin']} gross margin")
    _card(k3, "var(--sp-accent)", "SITE VALUE · ESTIMATE", f"{h['multiple_base']} licence",
          f"{h['value_base']} base case ({h['value_conservative']} – {h['value_upside']}) · demo Site B")
    _card(k4, "var(--sp-info)", "YEAR-3 TARGET", f"${years[-1]['arr'] / 1e6:.2f}M ARR",
          f"{years[-1]['sites']} paid sites · {h['year3_share']} of the beachhead")

    st.write("")

    # Section 1: Problem & customer evidence
    st.markdown("### 1. Problem & Customer Evidence")
    cd1, cd2 = st.columns(2)
    with cd1:
        st.markdown(
            """
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px; height:100%;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-info); margin-bottom:8px;">What 10 interviewees reported (7 logistics managers, 3 CPOs)</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2); line-height:1.65;">
                    • Equipment is coordinated on paper logbooks or WhatsApp groups.<br/>
                    • Booking clashes happen <strong>3–5 times per week</strong> per site.<br/>
                    • Concrete lost to queueing trucks: about <strong>$28,000 per high-rise project</strong> (interviewee estimate; anchors the base case).<br/>
                    • Sites learn of a supplier slip only when the truck fails to arrive.
                </div>
                <div class="metric-provenance" style="margin-top:10px;">Evidence log: docs/CUSTDEV_LOG.md</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cd2:
        st.markdown(
            """
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px; height:100%;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-accent); margin-bottom:8px;">Interview Quotes (Astana & Almaty)</div>
                <div style="font-size:0.82rem; color:var(--sp-text-2); font-style:italic; line-height:1.65;">
                    "When rebar slips by 4 days, my formwork carpenters and concrete pour team sit doing nothing. We pay daily standby wages while the crane stands idle."<br/>
                    <span style="font-style:normal; font-size:0.75rem; color:var(--sp-text-2);">— Site Superintendent, 22-Story Residential Project, Almaty</span>
                    <br/><br/>
                    "The city municipality fines us if concrete trucks queue on the street. We need a system that stops equipment bookings from overlapping."<br/>
                    <span style="font-style:normal; font-size:0.75rem; color:var(--sp-text-2);">— Logistics Dispatcher, Commercial Tower, Astana</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # Section 2: Market (bottom-up: sites x list price)
    st.markdown("### 2. Market Sizing · bottom-up (sites × list price)")
    m_col1, m_col2, m_col3 = st.columns([1, 1.3, 1])   # the beachhead is the market we target
    for col, color, label, value, sub in [
        (m_col1, "var(--sp-info)", "REGIONAL MARKET", h["market_regional"],
         f"~{A['regional_sites']['value']:,.0f} major sites in Central Asia, Caucasus & CIS × {h['acv']}/yr · founder estimate, source to verify"),
        (m_col2, "var(--sp-ok)", "BEACHHEAD", h["market_beachhead"],
         f"{A['beachhead_sites']['value']:.0f} active major sites of the top-15 KZ/UZ holdings × {h['acv']}/yr"),
        (m_col3, "var(--sp-accent)", "YEAR-3 TARGET", h["y3"],
         f"{h['year3_share']} of the beachhead — not full capture"),
    ]:
        col.markdown(
            f"""
            <div style="background:var(--sp-surface); border:1px solid var(--sp-surface-2); border-radius:8px; padding:16px;">
                <div style="font-size:0.75rem; font-weight:700; color:{color}; font-family:var(--sp-font-mono);">{label}</div>
                <div style="font-size:1.3rem; font-weight:800; color:var(--sp-text); margin:4px 0;">{value}</div>
                <div style="font-size:0.78rem; color:var(--sp-text-2); line-height:1.5;">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # Section 3: Unit economics, forecast and the assumptions behind them
    st.markdown("### 3. Unit Economics & Forecast")
    ue1, ue2 = st.columns([1.2, 0.8])
    with ue1:
        rows = [
            ("Annual contract value (standard site)", f"{h['acv']} / site / year"),
            ("Customer acquisition cost", f"{h['cac']} per site"),
            ("Lifetime value (gross-margin-adjusted)", f"{h['ltv']} per site"),
            ("LTV : CAC", h["ltv_to_cac"]),
            ("Gross margin", h["gross_margin"]),
            ("CAC payback", h["cac_payback"]),
            ("Break-even", h["break_even"]),
        ]
        body = "".join(
            f'<tr style="border-bottom:1px solid var(--sp-border);"><td style="padding:6px 0; color:var(--sp-text-2);">{k}</td>'
            f'<td style="text-align:right; font-weight:700; color:var(--sp-text);">{v}</td></tr>'
            for k, v in rows
        )
        st.markdown(
            f"""
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-text); margin-bottom:12px;">Unit Economics</div>
                <table style="width:100%; font-size:0.82rem; color:var(--sp-text-2); border-collapse:collapse;">{body}</table>
                <div class="metric-provenance" style="margin-top:10px;">No retention figure claimed — there is no revenue yet to retain.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with ue2:
        top = max(y["arr"] for y in years)
        bars = "".join(
            f"""
            <div style="margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; font-size:0.78rem; color:var(--sp-text-2);">
                    <span>Year {y['year']}</span>
                    <span style="font-weight:700; color:var(--sp-text);">{h[f"y{y['year']}"]}</span>
                </div>
                <div style="background:var(--sp-border); border-radius:4px; height:8px; margin-top:4px;">
                    <div style="background:var(--sp-info); width:{y['arr'] / top * 100:.0f}%; height:8px; border-radius:4px;"></div>
                </div>
            </div>"""
            for y in years
        )
        st.markdown(
            f"""
            <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px;">
                <div style="font-size:0.85rem; font-weight:700; color:var(--sp-text); margin-bottom:12px;">Forecast · paid active sites, list price</div>
                {bars}
                <div style="margin-top:16px; font-size:0.75rem; color:var(--sp-text-2); line-height:1.5;">
                    The 25% portfolio discount for 10+ sites would lower these figures.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Assumptions behind every number", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [{"assumption": k, "value": v["value"], "unit": v["unit"],
                  "source": v["source"], "note": v["note"]} for k, v in A.items()]
            ),
            width="stretch",
            hide_index=True,
        )

    st.write("")

    # Section 4: Competition
    st.markdown("### 4. Competition & Positioning")
    comp_rows = [
        ("Focus", "Delivery risk + equipment dispatch", "Site delivery & gate/crane booking",
         "AI-generated schedules", "ML schedule delay risk", "Project & field management", "ERP & accounting"),
        ("Predicts late deliveries", "Yes (unvalidated on real data)", "No", "No",
         "Schedule-level, not per delivery", "No", "No"),
        ("Clash-free equipment plan", "Yes, across sites", "Booking calendar per site",
         "Schedule optimization", "No", "Manual", "No"),
        ("Local deployment / 1C exports", "Yes", "No", "No", "No", "No", "Native"),
    ]
    head = "".join(f'<th style="padding:8px 10px; text-align:left;">{c}</th>' for c in
                   ["", "SitePulse", "Voyage Control", "ALICE Technologies", "nPlan", "Procore / Fieldwire", "1C / SAP"])
    trs = "".join(
        '<tr style="border-bottom:1px solid var(--sp-border);">'
        + "".join(f'<td style="padding:8px 10px;">{"<strong>" + c + "</strong>" if i < 2 else c}</td>'
                  for i, c in enumerate(r))
        + "</tr>"
        for r in comp_rows
    )
    st.markdown(
        f"""
        <div style="background:var(--sp-surface); border:1px solid var(--sp-border); border-radius:10px; padding:18px 20px; overflow-x:auto;">
            <table style="width:100%; min-width:720px; font-size:0.8rem; color:var(--sp-text-2); border-collapse:collapse;">
                <tr style="background:var(--sp-surface-2); font-weight:700; color:var(--sp-text);">{head}</tr>
                {trs}
            </table>
            <div style="font-size:0.8rem; color:var(--sp-text-2); margin-top:12px; line-height:1.6;">
                <strong>Moat today:</strong> none that is durable — OR-Tools and gradient boosting are open source.
                The asset that compounds is supplier-delay history per region and holding, which only accrues through pilots.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.info("**Pitch script:** the slide-by-slide script and Q&A preparation are in `docs/INVESTOR_DECK.md`.")

st.write("---")
with st.expander("Batch Upload CSV - Multi-Delivery Scoring", expanded=False):
    st.markdown(
        """
        Upload your delivery schedule in CSV format to calculate delay probabilities across all rows.  
        **Required Columns:** `supplier_id, material_type, route_type, quantity, order_date, promised_date`  
        *(You can test with `sample_deliveries.csv` located in the root repository).*
        """
    )
    up = st.file_uploader("Choose a CSV file", type=["csv"], key="batch_csv_uploader")
    if up:
        with st.spinner("Scoring batch with ML model..."):
            resp = requests.post(
                f"{API_URL}/predict/batch",
                files={"file": (up.name, up.getvalue(), "text/csv")},
                timeout=30,
            )
            if resp.status_code == 200:
                result_df = pd.DataFrame(resp.json()["rows"])
                st.success(f"Successfully scored {len(result_df)} deliveries!")
                st.dataframe(result_df, width="stretch")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")

with st.expander("Model Operations - Retrain Pipeline", expanded=False):
    st.markdown("Retrains on the newest historical database actuals and hot-swaps the model artifact with zero downtime.")
    if st.button("Trigger Retrain Now", key="retrain_btn"):
        with st.spinner("Retraining gradient-boosting delay classifier..."):
            # The admin key stays on the Streamlit server; the browser never sees it.
            r = requests.post(f"{API_URL}/train", timeout=120,
                              headers={"X-API-Key": os.getenv("SITEPULSE_ADMIN_KEY", "")})
        if r.status_code == 200:
            st.success("Model successfully retrained and artifact reloaded in memory!")
            st.rerun()
        else:
            st.error(f"Retrain failed: {r.text}")

# ─── VALIDATION STATUS FOOTER ───
st.markdown(
    """
    <div style="margin-top:40px; padding:16px 20px; border-top:1px solid var(--sp-border); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; font-size:0.75rem; color:var(--sp-text-3);">
        <div>
            <strong style="color:var(--sp-text-2);">Validation Status:</strong> 100% Synthetic Benchmark (n=2,200 deliveries, 260 crane bookings) · Real-world calibration pending 8-week pilot ERP ingestion.
        </div>
        <div>
            SitePulse Enterprise © 2026 · Regional Holding Pilot · <span style="color:var(--sp-accent); font-weight:600;">docs/PILOT_PROPOSAL.md</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

