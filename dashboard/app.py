"""Streamlit dashboard for BI Group delivery-delay risk.

Talks to the FastAPI service over HTTP (API_URL). Two views:
  * Upload CSV  -> score deliveries, color-coded risk table, per-row "why"
  * Browse projects -> seeded deliveries with predicted risk vs. actual status

Run:  streamlit run dashboard/app.py   (with the API already running)
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

BAND_COLOR = {"red": "#f8d7da", "yellow": "#fff3cd", "green": "#d1e7dd"}
DISPLAY_COLS = ["delivery_id", "supplier_id", "material_type", "route_type",
                "quantity", "order_date", "promised_date", "risk", "risk_band",
                "supplier_late_rate", "supplier_n_prior", "lead_time_days", "status"]

st.set_page_config(page_title="BI Group — Delivery Delay Risk", layout="wide")


def api_get(path: str, **params):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _color_rows(row):
    return [f"background-color: {BAND_COLOR.get(row['risk_band'], '')}"] * len(row)


def show_scored_table(df: pd.DataFrame, context: str) -> None:
    cols = [c for c in DISPLAY_COLS if c in df.columns]
    fmt = {c: "{:.2f}" for c in ("risk", "supplier_late_rate") if c in cols}
    st.dataframe(
        df[cols].style.apply(_color_rows, axis=1).format(fmt),
        use_container_width=True, height=430,
    )

    labels = [
        f"#{df.iloc[i].get('delivery_id', i)} · {df.iloc[i]['supplier_id']} · "
        f"{df.iloc[i]['material_type']} · risk {df.iloc[i]['risk']:.2f}"
        for i in range(len(df))
    ]
    i = st.selectbox("Inspect a delivery", range(len(df)),
                     format_func=lambda k: labels[k], key=f"sel_{context}")
    row = df.iloc[i]
    band = str(row["risk_band"]).upper()
    st.subheader(f"Why this delivery is {band} — risk {row['risk']:.2f}")
    drivers = row.get("drivers") or []
    if drivers:
        st.dataframe(pd.DataFrame(drivers), use_container_width=True, hide_index=True)
        st.caption("‘impact’ = how much each factor raised this delivery’s risk "
                   "versus a neutral value (occlusion attribution).")
    else:
        st.write("No single dominant risk driver for this delivery.")


st.title("🚧 Delivery-Delay Risk — BI Group")

try:
    health = api_get("/health")
    ap = api_get("/metrics")["ap"]
except Exception as exc:  # noqa: BLE001
    st.error(f"API not reachable at {API_URL}.\n\n"
             f"Start it with:  `uvicorn api.main:app --reload`\n\n{exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Model PR-AUC", f"{ap['model']:.3f}", f"{ap['lift']:+.3f} vs baseline")
c2.metric("Baseline PR-AUC", f"{ap['baseline']:.3f}")
c3.metric("Training rows", f"{health['trained_rows']:,}")
c4.metric("Features", health["n_features"])
st.caption("PR-AUC (Average Precision), 5-fold cross-validated. Baseline = "
           "supplier historical average. Demo runs on synthetic data.")

with st.expander("⚙️ Retrain model"):
    st.write("Retrain on the current data source and hot-swap the served model.")
    if st.button("Retrain now"):
        with st.spinner("Retraining…"):
            rr = requests.post(f"{API_URL}/train", timeout=300)
        if rr.status_code == 200:
            j = rr.json()
            st.success(f"Retrained on {j['trained_rows']} rows · "
                       f"PR-AUC {j['metrics']['ap']['model']:.3f} "
                       f"(lift {j['metrics']['ap']['lift']:+.3f} vs baseline)")
            st.rerun()
        else:
            st.error(f"{rr.status_code}: {rr.text}")

tab_upload, tab_browse = st.tabs(["📤 Upload CSV", "🏗️ Browse projects"])

with tab_upload:
    st.write("CSV columns required: "
             "`supplier_id, material_type, route_type, quantity, order_date, promised_date`")
    up = st.file_uploader("Deliveries CSV", type=["csv"])
    if up is None:
        st.info("Upload a CSV to score. Or explore the seeded data in the Browse tab.")
    else:
        resp = requests.post(f"{API_URL}/predict/batch",
                             files={"file": (up.name, up.getvalue(), "text/csv")},
                             timeout=120)
        if resp.status_code != 200:
            st.error(f"{resp.status_code}: {resp.json().get('detail')}")
        else:
            df = pd.DataFrame(resp.json()["rows"])
            st.success(f"Scored {len(df)} deliveries — sorted by risk (highest first).")
            show_scored_table(df, context="upload")

with tab_browse:
    pid = st.number_input("Project ID", min_value=1, max_value=4, value=1, step=1)
    try:
        data = api_get(f"/deliveries/{int(pid)}", limit=500)
        df = pd.DataFrame(data["deliveries"])
        counts = df["risk_band"].value_counts().to_dict()
        s1, s2, s3 = st.columns(3)
        s1.metric("🔴 High risk", counts.get("red", 0))
        s2.metric("🟡 Medium", counts.get("yellow", 0))
        s3.metric("🟢 Low", counts.get("green", 0))
        st.success(f"Project {int(pid)}: {len(df)} deliveries, risk-sorted "
                   "(predicted risk shown alongside actual status).")
        show_scored_table(df, context="browse")
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
