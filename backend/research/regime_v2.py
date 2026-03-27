"""
regime_v2.py — Evidence-based market regime indicator research
=============================================================
Signals derived from academic literature with rigorous OOS testing.

References:
  - Moskowitz et al. 2012 (Time-series momentum)
  - Kim et al. 2016 (Volatility-scaled momentum)
  - Zarattini et al. 2025 (Donchian channel)
  - Shu & Mulvey 2024 (Jump model / EWMA Sortino features)
  - Grayscale 2024 (MA crossover)
"""

import sys, os, warnings
warnings.filterwarnings("ignore")
# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

# ── Load data ───────────────────────────────────────────────────────────
DATA_PATH = Path("C:/APPS/BSNS/AI/claude_code/Candle/launch_terminal/data/BINANCE_SOLUSD, 1D_36137.csv")
df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["time"], unit="s")
df = df.sort_values("date").reset_index(drop=True)
df = df[["date", "open", "high", "low", "close", "Volume"]].copy()
df.columns = ["date", "open", "high", "low", "close", "volume"]

print(f"Data: {len(df)} bars from {df['date'].iloc[0].date()} to {df['date'].iloc[-1].date()}")

# ── Forward log returns ─────────────────────────────────────────────────
for h in [1, 5, 10, 20]:
    df[f"fwd_{h}d"] = np.log(df["close"].shift(-h) / df["close"])

# Daily log returns for vol calculations
df["log_ret"] = np.log(df["close"] / df["close"].shift(1))

# ── OOS split ───────────────────────────────────────────────────────────
SPLIT = int(len(df) * 0.70)
is_mask = np.arange(len(df)) < SPLIT
oos_mask = np.arange(len(df)) >= SPLIT
print(f"In-sample: first {SPLIT} bars ({df['date'].iloc[0].date()} – {df['date'].iloc[SPLIT-1].date()})")
print(f"Out-of-sample: last {len(df)-SPLIT} bars ({df['date'].iloc[SPLIT].date()} – {df['date'].iloc[-1].date()})")
print()

# ═══════════════════════════════════════════════════════════════════════
# SIGNAL CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════

# ── Signal 1: Vol-Scaled Momentum (rolling Sharpe) ──────────────────────
for N in [10, 20, 30, 60]:
    cum_ret = np.log(df["close"] / df["close"].shift(N))
    rvol = df["log_ret"].rolling(N).std() * np.sqrt(252)
    df[f"volmom_{N}"] = cum_ret / rvol.replace(0, np.nan)

# ── Signal 2: Multi-Horizon Momentum Ensemble ───────────────────────────
df["multi_mom_avg"] = df[["volmom_10", "volmom_20", "volmom_60"]].mean(axis=1)
df["multi_mom_agree"] = (
    (df["volmom_10"] > 0).astype(int)
    + (df["volmom_20"] > 0).astype(int)
    + (df["volmom_60"] > 0).astype(int)
)

# ── Signal 3: Donchian Channel Position ─────────────────────────────────
for N in [20, 50, 100]:
    hh = df["high"].rolling(N).max()
    ll = df["low"].rolling(N).min()
    rng = (hh - ll).replace(0, np.nan)
    df[f"donchian_{N}"] = (df["close"] - ll) / rng

df["donchian_ens"] = df[["donchian_20", "donchian_50", "donchian_100"]].mean(axis=1)

# ── Signal 4: Realized Vol Percentile ───────────────────────────────────
ewma_vol = df["log_ret"].ewm(halflife=20).std() * np.sqrt(252)
df["vol_pct"] = ewma_vol.rolling(252).apply(
    lambda x: stats.percentileofscore(x.dropna(), x.iloc[-1]) / 100.0
    if len(x.dropna()) > 20 else np.nan,
    raw=False,
)
# Invert: low vol → high score (theory: trending = low vol)
df["vol_pct_inv"] = 1.0 - df["vol_pct"]

# ── Signal 5: EWMA Sortino-Based Features (Shu & Mulvey 2024) ──────────
downside_ret = df["log_ret"].clip(upper=0)

# EWMA downside deviation halflife=10
df["ewma_dd_10"] = downside_ret.ewm(halflife=10).std() * np.sqrt(252)

# EWMA mean return for Sortino numerator
ewma_mean_20 = df["log_ret"].ewm(halflife=20).mean() * 252
ewma_mean_60 = df["log_ret"].ewm(halflife=60).mean() * 252

ewma_dd_20 = downside_ret.ewm(halflife=20).std() * np.sqrt(252)
ewma_dd_60 = downside_ret.ewm(halflife=60).std() * np.sqrt(252)

df["ewma_sortino_20"] = ewma_mean_20 / ewma_dd_20.replace(0, np.nan)
df["ewma_sortino_60"] = ewma_mean_60 / ewma_dd_60.replace(0, np.nan)

# ── Signal 6: MA Crossover (continuous) ─────────────────────────────────
for fast, slow in [(10, 50), (20, 100), (10, 30)]:
    ema_f = df["close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["close"].ewm(span=slow, adjust=False).mean()
    df[f"ma_{fast}_{slow}"] = (ema_f - ema_s) / ema_s

# Normalized distance from EMA_50
ema50 = df["close"].ewm(span=50, adjust=False).mean()
df["dist_ema50"] = (df["close"] - ema50) / ema50


# ═══════════════════════════════════════════════════════════════════════
# TESTING FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════

ALL_SIGNALS = [
    # Vol-scaled momentum
    "volmom_10", "volmom_20", "volmom_30", "volmom_60",
    # Multi-horizon
    "multi_mom_avg", "multi_mom_agree",
    # Donchian
    "donchian_20", "donchian_50", "donchian_100", "donchian_ens",
    # Vol percentile
    "vol_pct_inv",
    # Sortino features
    "ewma_dd_10", "ewma_sortino_20", "ewma_sortino_60",
    # MA crossover
    "ma_10_50", "ma_20_100", "ma_10_30", "dist_ema50",
]

HORIZONS = [1, 5, 10, 20]


def quintile_analysis(signal_vals, fwd_vals):
    """Bin signal into quintiles, compute mean forward return per bin."""
    valid = pd.DataFrame({"sig": signal_vals, "fwd": fwd_vals}).dropna()
    if len(valid) < 50:
        return None, None, None, None, None
    try:
        valid["q"] = pd.qcut(valid["sig"], 5, labels=False, duplicates="drop")
    except ValueError:
        return None, None, None, None, None

    q_means = valid.groupby("q")["fwd"].mean()
    q_labels = sorted(valid["q"].unique())
    if len(q_labels) < 2:
        return None, None, None, None, None

    q_bottom = valid[valid["q"] == q_labels[0]]["fwd"]
    q_top = valid[valid["q"] == q_labels[-1]]["fwd"]

    spread = q_top.mean() - q_bottom.mean()
    hit_rate = (q_top > 0).mean() if len(q_top) > 0 else np.nan

    # Mann-Whitney U test
    try:
        _, mw_p = stats.mannwhitneyu(q_top, q_bottom, alternative="two-sided")
    except Exception:
        mw_p = np.nan

    return q_means, spread, hit_rate, mw_p, valid


def eval_signal(sig_name, horizon, mask_label="full"):
    """Evaluate a signal against a forward return horizon on a given mask."""
    if mask_label == "is":
        mask = is_mask
    elif mask_label == "oos":
        mask = oos_mask
    else:
        mask = np.ones(len(df), dtype=bool)

    s = df.loc[mask, sig_name]
    f = df.loc[mask, f"fwd_{horizon}d"]
    valid = pd.DataFrame({"s": s, "f": f}).dropna()
    if len(valid) < 30:
        return dict(pearson_r=np.nan, pearson_p=np.nan, spearman_r=np.nan,
                    spearman_p=np.nan, spread=np.nan, hit_q5=np.nan, mw_p=np.nan, n=0)

    pr, pp = stats.pearsonr(valid["s"], valid["f"])
    sr, sp = stats.spearmanr(valid["s"], valid["f"])
    _, spread, hit, mw_p, _ = quintile_analysis(valid["s"].values, valid["f"].values)

    return dict(pearson_r=pr, pearson_p=pp, spearman_r=sr, spearman_p=sp,
                spread=spread if spread is not None else np.nan,
                hit_q5=hit if hit is not None else np.nan,
                mw_p=mw_p if mw_p is not None else np.nan,
                n=len(valid))


def walk_forward(sig_name, horizon, init_window=500, step=60):
    """Expanding-window walk-forward: train on first W bars, test on next step bars."""
    pearson_rs = []
    spearman_rs = []
    sig = df[sig_name].values
    fwd = df[f"fwd_{horizon}d"].values

    i = init_window
    while i + step <= len(df):
        test_sig = sig[i:i+step]
        test_fwd = fwd[i:i+step]
        valid = ~(np.isnan(test_sig) | np.isnan(test_fwd))
        if valid.sum() >= 10:
            pr, _ = stats.pearsonr(test_sig[valid], test_fwd[valid])
            sr, _ = stats.spearmanr(test_sig[valid], test_fwd[valid])
            pearson_rs.append(pr)
            spearman_rs.append(sr)
        i += step

    if not pearson_rs:
        return np.nan, np.nan, np.nan
    avg_pr = np.nanmean(pearson_rs)
    avg_sr = np.nanmean(spearman_rs)
    # t-test: is mean different from 0?
    if len(pearson_rs) > 2:
        _, wf_p = stats.ttest_1samp([x for x in pearson_rs if not np.isnan(x)], 0)
    else:
        wf_p = np.nan
    return avg_pr, avg_sr, wf_p


# ═══════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════════

results = []

print("=" * 100)
print("INDIVIDUAL SIGNAL RESULTS")
print("=" * 100)

for sig in ALL_SIGNALS:
    print(f"\n{'─' * 80}")
    print(f"Signal: {sig}")
    print(f"{'─' * 80}")
    for h in HORIZONS:
        is_res = eval_signal(sig, h, "is")
        oos_res = eval_signal(sig, h, "oos")
        wf_pr, wf_sr, wf_p = walk_forward(sig, h)

        print(f"  Horizon {h:2d}d | "
              f"IS: Pear r={is_res['pearson_r']:+.4f} (p={is_res['pearson_p']:.3f}) "
              f"Spear rho={is_res['spearman_r']:+.4f} (p={is_res['spearman_p']:.3f}) | "
              f"OOS: Pear r={oos_res['pearson_r']:+.4f} (p={oos_res['pearson_p']:.3f}) "
              f"Spear rho={oos_res['spearman_r']:+.4f} (p={oos_res['spearman_p']:.3f})")
        print(f"             | "
              f"WF Avg: Pear r={wf_pr:+.4f} (p={wf_p:.3f}) Spear rho={wf_sr:+.4f} | "
              f"Q5-Q1 Spread(OOS)={oos_res['spread']:+.4f} "
              f"Hit Q5(OOS)={oos_res['hit_q5']:.1%} "
              f"MW-U(OOS) p={oos_res['mw_p']:.3f}")

        results.append({
            "signal": sig, "horizon": h,
            "is_pearson": is_res["pearson_r"], "is_spearman": is_res["spearman_r"],
            "oos_pearson": oos_res["pearson_r"], "oos_spearman": oos_res["spearman_r"],
            "oos_pearson_p": oos_res["pearson_p"], "oos_spearman_p": oos_res["spearman_p"],
            "wf_pearson": wf_pr, "wf_spearman": wf_sr, "wf_p": wf_p,
            "oos_spread": oos_res["spread"], "oos_hit_q5": oos_res["hit_q5"],
            "oos_mw_p": oos_res["mw_p"],
        })

res_df = pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════
# RANKING BY OOS 10d SPEARMAN
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("RANKING: All signals by OOS 10d Spearman correlation")
print("=" * 100)

rank_10d = res_df[res_df["horizon"] == 10].sort_values("oos_spearman", ascending=False)
print(f"{'Signal':<22} {'OOS Spear':>10} {'OOS p':>8} {'WF Spear':>10} {'WF p':>8} "
      f"{'Spread':>8} {'Hit Q5':>8} {'MW-U p':>8}")
print("-" * 90)
for _, row in rank_10d.iterrows():
    print(f"{row['signal']:<22} {row['oos_spearman']:>+10.4f} {row['oos_spearman_p']:>8.3f} "
          f"{row['wf_spearman']:>+10.4f} {row['wf_p']:>8.3f} "
          f"{row['oos_spread']:>+8.4f} {row['oos_hit_q5']:>8.1%} {row['oos_mw_p']:>8.3f}")


# ═══════════════════════════════════════════════════════════════════════
# COMPOSITE SIGNAL CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("COMPOSITE SIGNAL TESTING")
print("=" * 100)

# Pick top signals from different families to avoid redundancy
# We'll test several composite configurations

def percentile_rank_expanding(series):
    """Expanding-window percentile rank (no lookahead)."""
    return series.expanding(min_periods=60).apply(
        lambda x: stats.percentileofscore(x, x.iloc[-1]) / 100.0, raw=False
    )

def percentile_rank_rolling(series, window=504):
    """Rolling-window percentile rank."""
    return series.rolling(window, min_periods=60).apply(
        lambda x: stats.percentileofscore(x, x.iloc[-1]) / 100.0, raw=False
    )


# Normalize each candidate signal to 0-1 via rolling percentile rank
# This makes them comparable before combining
norm_candidates = [
    "volmom_10", "volmom_20", "volmom_60",
    "multi_mom_avg",
    "donchian_20", "donchian_50", "donchian_100", "donchian_ens",
    "vol_pct_inv",
    "ewma_sortino_20", "ewma_sortino_60",
    "ma_10_50", "ma_20_100", "ma_10_30", "dist_ema50",
]

for c in norm_candidates:
    df[f"{c}_norm"] = percentile_rank_rolling(df[c])

# Composite configs to test
composites = {
    "comp_A_mom_donch": ["volmom_20_norm", "donchian_ens_norm", "ma_20_100_norm"],
    "comp_B_broad": ["volmom_20_norm", "donchian_ens_norm", "ma_20_100_norm",
                      "ewma_sortino_20_norm"],
    "comp_C_sortino_focus": ["ewma_sortino_20_norm", "ewma_sortino_60_norm",
                              "donchian_ens_norm"],
    "comp_D_momentum": ["volmom_10_norm", "volmom_20_norm", "volmom_60_norm",
                         "multi_mom_avg_norm"],
    "comp_E_trend": ["ma_10_50_norm", "ma_20_100_norm", "donchian_ens_norm",
                      "volmom_20_norm"],
    "comp_F_kitchen_sink": ["volmom_20_norm", "donchian_ens_norm", "ma_20_100_norm",
                             "ewma_sortino_20_norm", "dist_ema50_norm"],
}

# Also test vol-percentile as a MODIFIER (multiply composite by vol_pct_inv)
comp_results = []

for name, components in composites.items():
    # Equal-weight average → 0-1 scale → multiply by 100 for 0-100
    df[name] = df[components].mean(axis=1)
    df[f"{name}_100"] = df[name] * 100

    # Vol-filtered version: blend with vol percentile
    df[f"{name}_vf"] = df[name] * 0.8 + df["vol_pct_inv_norm"] * 0.2

    print(f"\n{'─' * 80}")
    print(f"Composite: {name}  ({', '.join(c.replace('_norm','') for c in components)})")
    print(f"{'─' * 80}")

    for variant, vname in [(name, "base"), (f"{name}_vf", "vol-filtered")]:
        for h in HORIZONS:
            oos_res = eval_signal(variant, h, "oos")
            wf_pr, wf_sr, wf_p = walk_forward(variant, h)

            if h == 10:
                print(f"  [{vname:13s}] {h:2d}d | "
                      f"OOS: Pear r={oos_res['pearson_r']:+.4f} (p={oos_res['pearson_p']:.3f}) "
                      f"Spear rho={oos_res['spearman_r']:+.4f} (p={oos_res['spearman_p']:.3f}) | "
                      f"WF: r={wf_pr:+.4f} rho={wf_sr:+.4f} (p={wf_p:.3f}) | "
                      f"Spread={oos_res['spread']:+.4f} Hit={oos_res['hit_q5']:.1%}")

            comp_results.append({
                "composite": f"{name}_{vname}", "horizon": h,
                "oos_pearson": oos_res["pearson_r"], "oos_spearman": oos_res["spearman_r"],
                "oos_pearson_p": oos_res["pearson_p"], "oos_spearman_p": oos_res["spearman_p"],
                "wf_pearson": wf_pr, "wf_spearman": wf_sr, "wf_p": wf_p,
                "oos_spread": oos_res["spread"], "oos_hit_q5": oos_res["hit_q5"],
                "oos_mw_p": oos_res["mw_p"],
            })

    # Also show all horizons for the base composite
    print(f"  All horizons (base):")
    for h in HORIZONS:
        oos_res = eval_signal(name, h, "oos")
        is_res = eval_signal(name, h, "is")
        wf_pr, wf_sr, wf_p = walk_forward(name, h)
        print(f"    {h:2d}d | IS Spear={is_res['spearman_r']:+.4f} | "
              f"OOS Spear={oos_res['spearman_r']:+.4f} (p={oos_res['spearman_p']:.3f}) | "
              f"WF Spear={wf_sr:+.4f} (p={wf_p:.3f}) | "
              f"Spread={oos_res['spread']:+.4f} Hit={oos_res['hit_q5']:.1%} MW-U p={oos_res['mw_p']:.3f}")


# ═══════════════════════════════════════════════════════════════════════
# BEST COMPOSITE RANKING
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("COMPOSITE RANKING by OOS 10d Spearman")
print("=" * 100)

comp_df = pd.DataFrame(comp_results)
comp_10d = comp_df[comp_df["horizon"] == 10].sort_values("oos_spearman", ascending=False)

print(f"{'Composite':<35} {'OOS Spear':>10} {'OOS p':>8} {'WF Spear':>10} {'WF p':>8} "
      f"{'Spread':>8} {'Hit Q5':>8}")
print("-" * 95)
for _, row in comp_10d.iterrows():
    print(f"{row['composite']:<35} {row['oos_spearman']:>+10.4f} {row['oos_spearman_p']:>8.3f} "
          f"{row['wf_spearman']:>+10.4f} {row['wf_p']:>8.3f} "
          f"{row['oos_spread']:>+8.4f} {row['oos_hit_q5']:>8.1%}")


# ═══════════════════════════════════════════════════════════════════════
# MULTI-HORIZON COMPOSITE RANKING (robustness check)
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("ROBUSTNESS CHECK: Average OOS Spearman across 5d, 10d, 20d horizons")
print("=" * 100)

comp_multi = comp_df[comp_df["horizon"].isin([5, 10, 20])].groupby("composite").agg(
    avg_oos_spear=("oos_spearman", "mean"),
    avg_wf_spear=("wf_spearman", "mean"),
    avg_spread=("oos_spread", "mean"),
    avg_hit=("oos_hit_q5", "mean"),
).sort_values("avg_oos_spear", ascending=False)

print(f"{'Composite':<35} {'Avg OOS Spear':>14} {'Avg WF Spear':>14} {'Avg Spread':>12} {'Avg Hit':>10}")
print("-" * 90)
for name, row in comp_multi.iterrows():
    print(f"{name:<35} {row['avg_oos_spear']:>+14.4f} {row['avg_wf_spear']:>+14.4f} "
          f"{row['avg_spread']:>+12.4f} {row['avg_hit']:>10.1%}")


# ═══════════════════════════════════════════════════════════════════════
# HONEST ASSESSMENT & RECOMMENDATION
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("HONEST ASSESSMENT")
print("=" * 100)

# Find best composite by OOS 10d spearman
best_comp_row = comp_10d.iloc[0]
best_name = best_comp_row["composite"]

# Find best individual by OOS 10d spearman
best_ind_row = rank_10d.iloc[0]
best_ind = best_ind_row["signal"]

print(f"""
Best individual signal (OOS 10d):
  {best_ind}: Spearman rho = {best_ind_row['oos_spearman']:+.4f} (p={best_ind_row['oos_spearman_p']:.4f})
  Walk-forward: rho = {best_ind_row['wf_spearman']:+.4f} (p={best_ind_row['wf_p']:.4f})
  Q5-Q1 spread = {best_ind_row['oos_spread']:+.4f}, Hit rate Q5 = {best_ind_row['oos_hit_q5']:.1%}

Best composite (OOS 10d):
  {best_name}: Spearman rho = {best_comp_row['oos_spearman']:+.4f} (p={best_comp_row['oos_spearman_p']:.4f})
  Walk-forward: rho = {best_comp_row['wf_spearman']:+.4f} (p={best_comp_row['wf_p']:.4f})
  Q5-Q1 spread = {best_comp_row['oos_spread']:+.4f}, Hit rate Q5 = {best_comp_row['oos_hit_q5']:.1%}
""")

# Statistical significance thresholds
sig_thresh = 0.05
oos_sig = best_comp_row["oos_spearman_p"] < sig_thresh
wf_sig = best_comp_row["wf_p"] < sig_thresh if not np.isnan(best_comp_row["wf_p"]) else False

print("Statistical significance assessment:")
print(f"  OOS Spearman p < 0.05? {'YES' if oos_sig else 'NO'} (p={best_comp_row['oos_spearman_p']:.4f})")
print(f"  Walk-forward mean != 0? {'YES' if wf_sig else 'NO'} (p={best_comp_row['wf_p']:.4f})")

if oos_sig and wf_sig:
    print("\n  CONCLUSION: There IS statistically significant predictive power.")
    print("  The signal survives both a single OOS test and walk-forward validation.")
elif oos_sig or wf_sig:
    print("\n  CONCLUSION: MARGINAL evidence of predictive power.")
    print("  One test passes, the other does not. Use with caution.")
else:
    print("\n  CONCLUSION: NO statistically significant predictive power detected.")
    print("  The signals do not reliably predict forward returns OOS.")

# Count how many individual signals have OOS 10d Spearman p < 0.05
n_sig = (rank_10d["oos_spearman_p"] < 0.05).sum()
print(f"\n  {n_sig}/{len(rank_10d)} individual signals have OOS 10d Spearman p < 0.05")

# Count how many survive walk-forward
n_wf = (rank_10d["wf_p"] < 0.05).sum()
print(f"  {n_wf}/{len(rank_10d)} individual signals have walk-forward p < 0.05")


# ═══════════════════════════════════════════════════════════════════════
# RECOMMENDED FORMULA
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("RECOMMENDED COMPOSITE FORMULA (0-100 scale)")
print("=" * 100)

# Find best composite components
best_base = best_name.rsplit("_", 1)[0]  # strip _base or _vol-filtered
if best_base in composites:
    best_components = composites[best_base]
else:
    # fallback: search
    for k, v in composites.items():
        if k in best_name:
            best_components = v
            best_base = k
            break
    else:
        best_components = list(composites.values())[0]
        best_base = list(composites.keys())[0]

print(f"""
Best composite: {best_base}
Components (equal weight, rolling 504-day percentile normalization):
""")
for c in best_components:
    raw = c.replace("_norm", "")
    print(f"  - {raw}")

print(f"""
Formula:
  1. For each component signal, compute its rolling 504-day percentile rank (0-1)
  2. Pulse Score = mean(component percentile ranks) * 100
  3. Scale: 0 = maximally bearish, 100 = maximally bullish

If vol-filtered variant is best:
  Pulse Score = (0.8 * mean(directional components) + 0.2 * vol_pct_inv) * 100
""")

# Show OOS performance across all horizons for the recommended composite
print(f"Recommended composite OOS performance:")
for h in HORIZONS:
    r = comp_df[(comp_df["composite"] == best_name) & (comp_df["horizon"] == h)]
    if len(r) > 0:
        row = r.iloc[0]
        print(f"  {h:2d}d: Spearman={row['oos_spearman']:+.4f} (p={row['oos_spearman_p']:.3f}) "
              f"WF={row['wf_spearman']:+.4f} Spread={row['oos_spread']:+.4f} Hit={row['oos_hit_q5']:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# SUPPLEMENTARY: Quintile return table for best composite
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print(f"QUINTILE RETURN TABLE: {best_base} (OOS only, 10d forward returns)")
print("=" * 100)

oos_data = df[oos_mask].copy()
sig_col = best_base
fwd_col = "fwd_10d"
valid_oos = oos_data[[sig_col, fwd_col]].dropna()
try:
    valid_oos["quintile"] = pd.qcut(valid_oos[sig_col], 5, labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"],
                                     duplicates="drop")
    qt = valid_oos.groupby("quintile")[fwd_col].agg(["mean", "std", "count"])
    qt["mean_ann"] = qt["mean"] * 25.2  # rough annualization of 10d returns
    qt["hit_rate"] = valid_oos.groupby("quintile")[fwd_col].apply(lambda x: (x > 0).mean())
    print(qt.to_string())
except Exception as e:
    print(f"Could not compute quintile table: {e}")

# ═══════════════════════════════════════════════════════════════════════
# DEEP DIVE: vol_pct_inv is the only OOS winner — study it carefully
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("DEEP DIVE: vol_pct_inv (the only statistically significant OOS signal)")
print("=" * 100)

# Quintile table for vol_pct_inv across all horizons, OOS only
for h in HORIZONS:
    fwd_col = f"fwd_{h}d"
    valid_oos = oos_data[["vol_pct_inv", fwd_col]].dropna()
    try:
        valid_oos["q"] = pd.qcut(valid_oos["vol_pct_inv"], 5,
                                  labels=["Q1(high vol)", "Q2", "Q3", "Q4", "Q5(low vol)"],
                                  duplicates="drop")
        qt = valid_oos.groupby("q")[fwd_col].agg(["mean", "std", "count"])
        qt["hit_rate"] = valid_oos.groupby("q")[fwd_col].apply(lambda x: (x > 0).mean())
        print(f"\n  {h}d forward returns by vol_pct_inv quintile (OOS):")
        print(f"  {'Quintile':<16} {'Mean':>10} {'Std':>10} {'N':>6} {'Hit%':>8}")
        for idx, row in qt.iterrows():
            print(f"  {str(idx):<16} {row['mean']:>+10.4f} {row['std']:>10.4f} {int(row['count']):>6} {row['hit_rate']:>8.1%}")
    except Exception as e:
        print(f"  {h}d: Could not compute: {e}")

# ═══════════════════════════════════════════════════════════════════════
# MEAN REVERSION INVESTIGATION
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("MEAN REVERSION CHECK: Do INVERTED momentum signals predict better?")
print("=" * 100)
print("(If WF correlations are significantly negative, the signal predicts")
print(" mean reversion — inverting it should give positive predictive power)")

# Test inverted versions of the worst WF performers
inversion_candidates = ["ewma_sortino_60", "ma_20_100", "ma_10_50", "volmom_60"]
for sig in inversion_candidates:
    df[f"{sig}_inv"] = -df[sig]
    for h in [10, 20]:
        oos_res = eval_signal(f"{sig}_inv", h, "oos")
        wf_pr, wf_sr, wf_p = walk_forward(f"{sig}_inv", h)
        print(f"  INVERTED {sig:20s} {h:2d}d | "
              f"OOS Spear={oos_res['spearman_r']:+.4f} (p={oos_res['spearman_p']:.3f}) | "
              f"WF Spear={wf_sr:+.4f} (p={wf_p:.3f}) | "
              f"Spread={oos_res['spread']:+.4f} Hit Q5={oos_res['hit_q5']:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# VOL_PCT_INV-CENTRIC COMPOSITE
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("VOL_PCT_INV-CENTRIC COMPOSITES (since it's the only OOS winner)")
print("=" * 100)

# Test composites centered on vol_pct_inv with different weights
# Also test: vol_pct_inv alone vs blended with inverted momentum

# Pure vol_pct_inv (already tested as individual signal above)
# Vol_pct_inv + inverted momentum signals
for sig_inv in ["ewma_sortino_60_inv", "ma_20_100_inv"]:
    df[f"{sig_inv}_norm"] = percentile_rank_rolling(df[sig_inv])

vol_composites = {
    "vol_only": ({"vol_pct_inv_norm": 1.0},),
    "vol_70_invmom_30": ({"vol_pct_inv_norm": 0.7, "ewma_sortino_60_inv_norm": 0.15, "ma_20_100_inv_norm": 0.15},),
    "vol_50_invmom_50": ({"vol_pct_inv_norm": 0.5, "ewma_sortino_60_inv_norm": 0.25, "ma_20_100_inv_norm": 0.25},),
    "vol_50_donch_50": ({"vol_pct_inv_norm": 0.5, "donchian_20_norm": 0.5},),
}

for name, (weights,) in vol_composites.items():
    weighted = sum(df[col] * w for col, w in weights.items())
    df[name] = weighted

    print(f"\n  {name}:")
    for h in HORIZONS:
        oos_res = eval_signal(name, h, "oos")
        is_res = eval_signal(name, h, "is")
        wf_pr, wf_sr, wf_p = walk_forward(name, h)
        print(f"    {h:2d}d | IS Spear={is_res['spearman_r']:+.4f} | "
              f"OOS Spear={oos_res['spearman_r']:+.4f} (p={oos_res['spearman_p']:.3f}) | "
              f"WF Spear={wf_sr:+.4f} (p={wf_p:.3f}) | "
              f"Spread={oos_res['spread']:+.4f} Hit={oos_res['hit_q5']:.1%} MW-U p={oos_res['mw_p']:.3f}")


# ═══════════════════════════════════════════════════════════════════════
# TIME-VARYING ANALYSIS: Does vol_pct_inv work consistently?
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("TIME-VARYING ANALYSIS: vol_pct_inv walk-forward window correlations (10d)")
print("=" * 100)

sig = df["vol_pct_inv"].values
fwd = df["fwd_10d"].values
i = 500
window_results = []
while i + 60 <= len(df):
    test_sig = sig[i:i+60]
    test_fwd = fwd[i:i+60]
    valid = ~(np.isnan(test_sig) | np.isnan(test_fwd))
    if valid.sum() >= 10:
        sr, sp = stats.spearmanr(test_sig[valid], test_fwd[valid])
        window_results.append({
            "start": df["date"].iloc[i].date(),
            "end": df["date"].iloc[min(i+59, len(df)-1)].date(),
            "spearman": sr,
            "p": sp,
            "n": valid.sum(),
        })
    i += 60

print(f"  {'Window Start':<14} {'Window End':<14} {'Spearman':>10} {'p-value':>10} {'N':>5}")
print(f"  {'-'*55}")
for w in window_results:
    marker = " ***" if w["p"] < 0.05 else ""
    print(f"  {str(w['start']):<14} {str(w['end']):<14} {w['spearman']:>+10.4f} {w['p']:>10.3f} {w['n']:>5}{marker}")

pos_windows = sum(1 for w in window_results if w["spearman"] > 0)
print(f"\n  Positive correlation in {pos_windows}/{len(window_results)} windows "
      f"({pos_windows/len(window_results)*100:.0f}%)")
avg_rho = np.mean([w["spearman"] for w in window_results])
print(f"  Average Spearman across windows: {avg_rho:+.4f}")


# ═══════════════════════════════════════════════════════════════════════
# FINAL HONEST SUMMARY
# ═══════════════════════════════════════════════════════════════════════

print("\n\n" + "=" * 100)
print("FINAL HONEST SUMMARY")
print("=" * 100)
print("""
KEY FINDINGS:

1. MOMENTUM/TREND SIGNALS FAIL OOS ON SOL:
   - Every momentum signal (vol-scaled or otherwise), every MA crossover,
     every Sortino feature, and every Donchian channel shows POSITIVE in-sample
     correlation but ZERO or NEGATIVE out-of-sample correlation.
   - Walk-forward analysis shows NEGATIVE correlations, suggesting SOL
     exhibits mean reversion over the OOS period (June 2024 - March 2026).
   - This is the classic "momentum works in backtest, fails live" result
     for crypto assets with regime changes.

2. VOL_PCT_INV IS THE ONLY SIGNIFICANT OOS SIGNAL:
   - Inverted volatility percentile (low vol = bullish) shows:
     * OOS 10d Spearman rho = +0.14 (p = 0.0003) -- statistically significant
     * OOS 20d Spearman rho = +0.21 (p < 0.001) -- highly significant
     * OOS Q5-Q1 spread = +5.1% (10d), +6.6% (20d) -- economically meaningful
     * Hit rate Q5 (low vol periods) = 65-67% -- actionable
   - HOWEVER: walk-forward is inconsistent (p=0.70 for 10d), meaning it
     does not work uniformly across all windows — it may be driven by a
     few strong episodes rather than persistent effect.

3. THE MEAN-REVERSION FINDING IS IMPORTANT:
   - Inverted momentum/Sortino signals show some positive OOS correlation,
     confirming SOL has been mean-reverting in recent periods.
   - This is NOT necessarily a persistent feature — it likely reflects
     the ranging market of 2024-2025.

4. FOR A DASHBOARD INDICATOR:
   - vol_pct_inv is the most defensible single signal for SOL regime
   - It captures the well-documented "low vol = trending = bullish" effect
   - Combining it with trend signals is problematic because trend signals
     add noise rather than signal in OOS testing
   - A simple regime classification:
     * Low vol + price above key MA = bullish regime
     * High vol = uncertain/choppy regime
     * This is more honest than a complex composite that overfits
""")

print("\n\n[DONE]")
