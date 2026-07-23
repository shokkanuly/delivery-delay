"""Problems 2 & 3 -- leakage-free features and graceful cold-start.

THE KEY IDEA (Problem 2): every feature derived from the target (`is_late`) is
computed *causally*. For a given delivery, we only ever look at other deliveries
that had already been COMPLETED (`actual_date`) strictly before this delivery was
ORDERED (`order_date`). That is exactly the information you would have had at
prediction time. Because a row's features depend only on rows in its past -- not
on any train/test fold assignment -- these features are safe under ordinary
k-fold CV without per-fold re-encoding (this is why train.py can use plain
StratifiedKFold and still be leakage-free).

COLD START (Problem 3): a brand-new supplier has no history, so its own late-rate
is undefined. Instead of dropping the row or imputing a NaN, we blend three
causal levels with empirical-Bayes shrinkage:

    supplier  --shrinks toward-->  material x route  --shrinks toward-->  global prior

`k_shrink` is how many observations of evidence it takes before the
supplier-specific rate is trusted over the fallback. `supplier_n_prior` is
exposed as its own feature so the model knows how much evidence backs the rate.

WEATHER (Problem 3): live forecasts are only trustworthy ~10 days out, but lead
times run to 45 days -- so at prediction time a forecast is often noise. We use a
seasonal NORMAL (climatology) for the promised month, which is always available
and honest. `blend_weather()` shows how to splice in a real short-horizon
forecast when you have one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Seasonal-normal severity by month (climatology), independent of any forecast.
_CLIMATOLOGY = {
    1: 0.90, 2: 0.80, 3: 0.50, 4: 0.30, 5: 0.10, 6: 0.05,
    7: 0.05, 8: 0.05, 9: 0.20, 10: 0.45, 11: 0.65, 12: 0.85,
}
FORECAST_HORIZON_DAYS = 10  # beyond this, forecasts are unreliable -> use normals


def seasonal_severity(month: int) -> float:
    return _CLIMATOLOGY.get(int(month), 0.3)


def blend_weather(month: int, lead_time_days: int, forecast_severity: float | None):
    """Use a real forecast only inside the reliable horizon; else climatology."""
    if forecast_severity is not None and lead_time_days <= FORECAST_HORIZON_DAYS:
        return float(forecast_severity)
    return seasonal_severity(month)


def shrink(sum_, n, fallback, k):
    """Empirical-Bayes shrink: blend an observed rate toward a fallback, trusting
    the observation more as its sample size n grows. Works on scalars or arrays."""
    return (sum_ + k * fallback) / (n + k)


def _causal_components(df: pd.DataFrame, key_cols, target_col: str):
    """For each row: (sum, count) of `target_col` over prior COMPLETED rows that
    share the key. "Prior" = actual_date strictly before this row's order_date.

    O(n log n) per group via sort + searchsorted; fine well past MVP scale.
    """
    n = len(df)
    prior_sum = np.zeros(n)
    prior_cnt = np.zeros(n)
    order_all = df["order_date"].to_numpy()          # datetime64[ns]
    done_all = df["actual_date"].to_numpy()
    tgt_all = df[target_col].to_numpy(dtype=float)

    if key_cols is None:  # global: treat the whole frame as one group
        groups = {None: np.arange(n)}
    else:
        groups = df.groupby(key_cols, sort=False).indices

    for idx in groups.values():
        idx = np.asarray(idx)
        done_g = done_all[idx]
        order = np.argsort(done_g, kind="mergesort")   # sort this group by completion
        done_sorted = done_g[order]
        cum = np.concatenate([[0.0], np.cumsum(tgt_all[idx][order])])
        # count / sum of completions strictly before each row's order_date
        pos = np.searchsorted(done_sorted, order_all[idx], side="left")
        prior_cnt[idx] = pos
        prior_sum[idx] = cum[pos]
    return prior_sum, prior_cnt


def build_features(
    df: pd.DataFrame,
    k_shrink: float = 8.0,
    prior_late_rate: float = 0.35,
    leaky: bool = False,
):
    """Return (X, y, enriched_df).

    `leaky=True` intentionally builds the WRONG version (full-sample group means
    that peek at the future) so train.py can quantify the leakage mirage. Never
    use it for a real model.
    """
    df = df.sort_values("order_date").reset_index(drop=True)
    y = df["is_late"].astype(int)

    if leaky:
        # WRONG ON PURPOSE: transform("mean") uses every row in the group,
        # including deliveries that happen AFTER this one. This is the single
        # most common way delivery-delay demos report fantasy accuracy.
        supplier_late_rate = df.groupby("supplier_id")["is_late"].transform("mean").to_numpy()
        supplier_n_prior = df.groupby("supplier_id")["is_late"].transform("size").to_numpy()
        mr_late_rate = (
            df.groupby(["material_type", "route_type"])["is_late"].transform("mean").to_numpy()
        )
    else:
        # --- causal, cold-start-safe hierarchy -------------------------------
        g_sum, g_cnt = _causal_components(df, None, "is_late")
        global_rate = shrink(g_sum, g_cnt, prior_late_rate, k_shrink)

        mr_sum, mr_cnt = _causal_components(df, ["material_type", "route_type"], "is_late")
        mr_late_rate = shrink(mr_sum, mr_cnt, global_rate, k_shrink)

        s_sum, s_cnt = _causal_components(df, ["supplier_id"], "is_late")
        supplier_late_rate = shrink(s_sum, s_cnt, mr_late_rate, k_shrink)
        supplier_n_prior = s_cnt

    lead_time = (df["promised_date"] - df["order_date"]).dt.days
    month = df["promised_date"].dt.month

    X = pd.DataFrame(index=df.index)
    X["supplier_late_rate"] = supplier_late_rate    # main signal (= the baseline)
    X["supplier_n_prior"] = supplier_n_prior        # evidence strength
    X["mr_late_rate"] = mr_late_rate                # fallback signal for cold rows
    X["lead_time_days"] = lead_time
    X["promised_month"] = month
    X["promised_dow"] = df["promised_date"].dt.dayofweek
    X["quantity"] = df["quantity"]
    X["weather_severity"] = month.map(seasonal_severity)
    # low-cardinality categoricals: one-hot is fine and uses no target info
    X = pd.concat(
        [
            X,
            pd.get_dummies(df["material_type"], prefix="mat", dtype=float),
            pd.get_dummies(df["route_type"], prefix="route", dtype=float),
        ],
        axis=1,
    )

    enriched = df.copy()
    enriched["supplier_late_rate"] = supplier_late_rate
    enriched["supplier_n_prior"] = supplier_n_prior
    return X, y, enriched


def build_snapshot(df: pd.DataFrame, k_shrink: float = 8.0,
                   prior_late_rate: float = 0.35) -> dict:
    """Freeze the causal rate tables as of training time so /predict is stateless.

    At serve time every training delivery is, by definition, in the past relative
    to a future order -- so we aggregate over ALL rows here (not the causal
    expanding window used per-row during training). We store raw sum/count so the
    exact 3-level shrinkage can be reproduced at predict time.
    """
    mr = df.groupby(["material_type", "route_type"])["is_late"].agg(["sum", "size"])
    sup = df.groupby("supplier_id")["is_late"].agg(["sum", "size"])
    return {
        "k_shrink": float(k_shrink),
        "prior_late_rate": float(prior_late_rate),
        "global": {"sum": float(df["is_late"].sum()), "n": int(len(df))},
        "mr": {idx: {"sum": float(r["sum"]), "n": int(r["size"])}
               for idx, r in mr.iterrows()},
        "supplier": {sid: {"sum": float(r["sum"]), "n": int(r["size"])}
                     for sid, r in sup.iterrows()},
    }


def supplier_features_from_snapshot(snapshot, material_type, route_type, supplier_id):
    """Reproduce (supplier_late_rate, supplier_n_prior, mr_late_rate) for one
    delivery from the frozen snapshot -- identical shrinkage to training, with the
    same supplier -> material x route -> global cold-start fallback."""
    k = snapshot["k_shrink"]
    g = snapshot["global"]
    global_rate = shrink(g["sum"], g["n"], snapshot["prior_late_rate"], k)
    mr = snapshot["mr"].get((material_type, route_type))
    mr_rate = shrink(mr["sum"], mr["n"], global_rate, k) if mr else global_rate
    s = snapshot["supplier"].get(supplier_id)
    if s:
        return shrink(s["sum"], s["n"], mr_rate, k), int(s["n"]), mr_rate
    return mr_rate, 0, mr_rate  # cold start -> fall back to material x route


if __name__ == "__main__":
    from ml.data_sim import generate_deliveries
    from ml.labeling import add_labels

    d = add_labels(generate_deliveries())
    X, y, enr = build_features(d)
    cold = (enr["supplier_n_prior"] == 0).sum()
    print(f"{X.shape[1]} features, {len(X)} rows")
    print(f"cold-start rows (no supplier history): {cold} ({cold/len(X):.1%})")
    print(list(X.columns))
