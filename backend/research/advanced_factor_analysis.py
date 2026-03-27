"""
Advanced factor analysis — go beyond simple Pearson correlation.

Tests each factor against SOL forward returns using:
1. Pearson r (linear, baseline)
2. Spearman rho (rank-based, captures monotonic non-linear)
3. Mutual Information (captures ANY statistical dependency)
4. Quantile analysis (does extreme factor values predict extreme returns?)
5. Log-transformed correlation (compresses outliers, reveals underlying trend)
6. Conditional correlation (does the factor matter more in certain regimes?)
7. Granger causality (does the factor time-series actually predict returns?)
8. Interaction effects (do factor COMBINATIONS predict better than individuals?)
9. Rolling stability (is the signal consistent or just a lucky window?)
"""

import json
import sqlite3
import sys
from datetime import date, timedelta
from collections import defaultdict

import numpy as np
from scipy import stats
from scipy.stats import spearmanr, pearsonr, kendalltau
from sklearn.metrics import mutual_info_score
from sklearn.feature_selection import mutual_info_regression

# ---------- Data Loading ----------

def load_series(db_path: str, source: str) -> dict[date, float]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT date, value FROM historical_data WHERE source = ? ORDER BY date",
        (source,),
    )
    result = {}
    for row in cur.fetchall():
        d = date.fromisoformat(row[0])
        result[d] = float(row[1])
    conn.close()
    return result


def compute_forward_returns(prices: dict[date, float], days: int = 7) -> dict[date, float]:
    sorted_dates = sorted(prices.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future = prices[sorted_dates[target_idx]]
            current = prices[d]
            if current > 0:
                returns[d] = (future - current) / current
    return returns


def compute_returns(series: dict[date, float], days: int = 7) -> dict[date, float]:
    sorted_dates = sorted(series.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future = series[sorted_dates[target_idx]]
            current = series[d]
            if current != 0:
                returns[d] = (future - current) / abs(current)
    return returns


def align_series(
    factor: dict[date, float],
    target: dict[date, float],
    lag: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Align factor (lagged) with target returns. Returns paired arrays."""
    x, y = [], []
    for d, ret in target.items():
        lagged = d - timedelta(days=lag)
        if lagged in factor:
            x.append(factor[lagged])
            y.append(ret)
    return np.array(x), np.array(y)


# ---------- Test 1: Pearson (baseline) ----------

def test_pearson(x: np.ndarray, y: np.ndarray) -> dict:
    if len(x) < 30:
        return {"r": None, "p": None}
    r, p = pearsonr(x, y)
    return {"r": round(r, 4), "p": round(p, 6)}


# ---------- Test 2: Spearman (rank-based, captures monotonic non-linear) ----------

def test_spearman(x: np.ndarray, y: np.ndarray) -> dict:
    if len(x) < 30:
        return {"rho": None, "p": None}
    rho, p = spearmanr(x, y)
    return {"rho": round(rho, 4), "p": round(p, 6)}


# ---------- Test 3: Mutual Information (captures ANY dependency) ----------

def test_mutual_info(x: np.ndarray, y: np.ndarray) -> dict:
    if len(x) < 50:
        return {"mi": None}
    # mutual_info_regression expects 2D X
    mi = mutual_info_regression(x.reshape(-1, 1), y, random_state=42, n_neighbors=7)
    return {"mi": round(float(mi[0]), 4)}


# ---------- Test 4: Quantile analysis ----------

def test_quantile_returns(x: np.ndarray, y: np.ndarray, n_quantiles: int = 5) -> dict:
    """Split factor values into quantiles, compute mean forward return per quantile.

    If extreme factor values predict extreme returns, this will show it even when
    linear correlation is weak (e.g., U-shaped or threshold effects).
    """
    if len(x) < n_quantiles * 20:
        return {"quantile_returns": None, "spread": None}

    try:
        quantile_labels = np.digitize(x, np.percentile(x, np.linspace(0, 100, n_quantiles + 1)[1:-1]))
    except Exception:
        return {"quantile_returns": None, "spread": None}

    quantile_means = {}
    for q in range(n_quantiles):
        mask = quantile_labels == q
        if mask.sum() > 5:
            quantile_means[f"Q{q+1}"] = round(float(np.mean(y[mask])) * 100, 3)

    # Spread: difference between top and bottom quantile mean returns
    if f"Q1" in quantile_means and f"Q{n_quantiles}" in quantile_means:
        spread = quantile_means[f"Q{n_quantiles}"] - quantile_means["Q1"]
    else:
        spread = None

    # Statistical significance: Kruskal-Wallis test across quantiles
    groups = [y[quantile_labels == q] for q in range(n_quantiles) if (quantile_labels == q).sum() > 5]
    if len(groups) >= 2:
        h_stat, kw_p = stats.kruskal(*groups)
    else:
        h_stat, kw_p = None, None

    return {
        "quantile_returns_pct": quantile_means,
        "spread_pct": round(spread, 3) if spread is not None else None,
        "kruskal_wallis_p": round(kw_p, 6) if kw_p is not None else None,
    }


# ---------- Test 5: Log-transformed correlation ----------

def test_log_transform(x: np.ndarray, y: np.ndarray) -> dict:
    """Test correlation after log-transforming the factor values.

    Many financial series have log-normal distributions. Log transform
    compresses outliers and can reveal underlying linear relationships.
    """
    if len(x) < 30:
        return {"pearson_log": None, "spearman_log": None}

    # Handle negative values: use log(1 + x - min(x)) to shift to positive
    x_shifted = x - x.min() + 1
    x_log = np.log(x_shifted)

    r, p_r = pearsonr(x_log, y)
    rho, p_rho = spearmanr(x_log, y)
    return {
        "pearson_log_r": round(r, 4),
        "pearson_log_p": round(p_r, 6),
        "spearman_log_rho": round(rho, 4),
    }


# ---------- Test 6: Conditional / Regime-dependent correlation ----------

def test_conditional(x: np.ndarray, y: np.ndarray) -> dict:
    """Test if correlation changes in different regimes.

    Split by factor median: does the factor predict better when it's
    high vs low? Also split by return magnitude: does it predict
    in trending vs ranging markets?
    """
    if len(x) < 100:
        return {"high_regime_r": None, "low_regime_r": None}

    median_x = np.median(x)

    # Correlation when factor is above median
    high_mask = x >= median_x
    low_mask = x < median_x

    results = {}
    for name, mask in [("high_regime", high_mask), ("low_regime", low_mask)]:
        if mask.sum() >= 30:
            r, p = pearsonr(x[mask], y[mask])
            results[f"{name}_r"] = round(r, 4)
            results[f"{name}_p"] = round(p, 6)
            results[f"{name}_n"] = int(mask.sum())
        else:
            results[f"{name}_r"] = None

    # Is the difference significant? (Fisher z-test)
    if results.get("high_regime_r") is not None and results.get("low_regime_r") is not None:
        z1 = np.arctanh(results["high_regime_r"])
        z2 = np.arctanh(results["low_regime_r"])
        n1 = results["high_regime_n"]
        n2 = results["low_regime_n"]
        se = np.sqrt(1/(n1-3) + 1/(n2-3))
        z_diff = (z1 - z2) / se if se > 0 else 0
        results["regime_diff_z"] = round(z_diff, 3)
        results["regime_diff_p"] = round(2 * (1 - stats.norm.cdf(abs(z_diff))), 6)

    return results


# ---------- Test 7: Granger causality ----------

def test_granger(x: np.ndarray, y: np.ndarray, max_lag: int = 14) -> dict:
    """Simplified Granger causality: does adding lagged factor values improve
    prediction of returns beyond what lagged returns alone provide?

    Uses F-test comparing restricted (returns only) vs unrestricted (returns + factor) model.
    """
    if len(x) < max_lag + 50:
        return {"granger_f": None, "granger_p": None}

    n = len(y)

    # Build lagged matrices
    Y = y[max_lag:]

    # Restricted model: predict returns from own lags
    X_restricted = np.column_stack([y[max_lag-i-1:n-i-1] for i in range(max_lag)])

    # Unrestricted: own lags + factor lags
    X_unrestricted = np.column_stack([
        X_restricted,
        *[x[max_lag-i-1:n-i-1].reshape(-1, 1) for i in range(max_lag)]
    ])

    # Add intercept
    X_r = np.column_stack([np.ones(len(Y)), X_restricted])
    X_u = np.column_stack([np.ones(len(Y)), X_unrestricted])

    try:
        # OLS for restricted
        beta_r = np.linalg.lstsq(X_r, Y, rcond=None)[0]
        resid_r = Y - X_r @ beta_r
        sse_r = np.sum(resid_r ** 2)

        # OLS for unrestricted
        beta_u = np.linalg.lstsq(X_u, Y, rcond=None)[0]
        resid_u = Y - X_u @ beta_u
        sse_u = np.sum(resid_u ** 2)

        # F-test
        df_diff = X_u.shape[1] - X_r.shape[1]
        df_resid = len(Y) - X_u.shape[1]

        if sse_u > 0 and df_diff > 0 and df_resid > 0:
            f_stat = ((sse_r - sse_u) / df_diff) / (sse_u / df_resid)
            p_value = 1 - stats.f.cdf(f_stat, df_diff, df_resid)
            return {
                "granger_f": round(f_stat, 4),
                "granger_p": round(p_value, 6),
                "granger_significant": p_value < 0.05,
            }
    except Exception as e:
        return {"granger_error": str(e)}

    return {"granger_f": None, "granger_p": None}


# ---------- Test 8: Rolling stability ----------

def test_rolling_stability(x: np.ndarray, y: np.ndarray, window: int = 180) -> dict:
    """Compute rolling correlation to check if signal is stable or spurious.

    A factor with r=0.15 that's consistent across all windows is much more
    valuable than one with r=0.30 that only appears in one lucky period.
    """
    if len(x) < window + 60:
        return {"rolling_mean_r": None, "rolling_std_r": None}

    rolling_rs = []
    for i in range(0, len(x) - window, 30):  # step by 30 days
        xi = x[i:i+window]
        yi = y[i:i+window]
        if np.std(xi) > 0 and np.std(yi) > 0:
            r, _ = pearsonr(xi, yi)
            if np.isfinite(r):
                rolling_rs.append(r)

    if not rolling_rs:
        return {"rolling_mean_r": None}

    rs = np.array(rolling_rs)
    return {
        "rolling_mean_r": round(float(np.mean(rs)), 4),
        "rolling_std_r": round(float(np.std(rs)), 4),
        "rolling_min_r": round(float(np.min(rs)), 4),
        "rolling_max_r": round(float(np.max(rs)), 4),
        "pct_windows_positive": round(float(np.mean(rs > 0)) * 100, 1),
        "pct_windows_significant": round(float(np.mean(np.abs(rs) > 0.15)) * 100, 1),
        "n_windows": len(rolling_rs),
    }


# ---------- Test 9: Non-linear transforms ----------

def test_nonlinear_transforms(x: np.ndarray, y: np.ndarray) -> dict:
    """Test if non-linear transforms of the factor improve correlation.

    - Squared: captures U-shaped relationships (both extremes matter)
    - Absolute deviation from mean: captures "unusual values predict movement"
    - Percentile rank: normalizes; removes scale effects
    - Rate of change: momentum of the factor itself
    """
    if len(x) < 50:
        return {}

    results = {}

    # Squared (captures U-shape: both high AND low values predict same direction)
    x_sq = (x - np.mean(x)) ** 2
    r, p = pearsonr(x_sq, y)
    results["squared_r"] = round(r, 4)
    results["squared_p"] = round(p, 6)

    # Absolute deviation from mean (captures "unusual = predictive")
    x_absdev = np.abs(x - np.mean(x))
    r, p = pearsonr(x_absdev, y)
    results["absdev_r"] = round(r, 4)
    results["absdev_p"] = round(p, 6)

    # Percentile rank (non-parametric normalization)
    x_rank = stats.rankdata(x) / len(x)
    r, p = pearsonr(x_rank, y)
    results["rank_r"] = round(r, 4)
    results["rank_p"] = round(p, 6)

    return results


# ---------- Test 10: Multi-factor interaction ----------

def test_interactions(
    factors: dict[str, np.ndarray],
    y: np.ndarray,
    dates: np.ndarray,
) -> dict:
    """Test if factor COMBINATIONS predict better than individuals.

    - Pairwise products (interaction terms)
    - PCA on all factors (find hidden composite signal)
    - Simple ensemble: average z-score across all factors
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    names = list(factors.keys())
    if len(names) < 2:
        return {}

    # Stack all factors, align dates
    common_idx = np.arange(len(y))
    X = np.column_stack([factors[n] for n in names])

    if len(X) < 50:
        return {}

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    results = {}

    # Pairwise interaction terms
    interaction_results = {}
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            interaction = X_scaled[:, i] * X_scaled[:, j]
            r, p = pearsonr(interaction, y)
            key = f"{names[i]}*{names[j]}"
            if abs(r) > 0.05:  # only report non-trivial
                interaction_results[key] = {"r": round(r, 4), "p": round(p, 6)}
    results["interactions"] = interaction_results

    # PCA: find composite signal
    if X_scaled.shape[1] >= 2:
        pca = PCA(n_components=min(3, X_scaled.shape[1]))
        X_pca = pca.fit_transform(X_scaled)
        pca_results = {}
        for pc in range(X_pca.shape[1]):
            r, p = pearsonr(X_pca[:, pc], y)
            pca_results[f"PC{pc+1}"] = {
                "r": round(r, 4),
                "p": round(p, 6),
                "variance_explained": round(float(pca.explained_variance_ratio_[pc]), 4),
            }
        results["pca"] = pca_results

    # Ensemble z-score (simple average of all standardized factors)
    ensemble = np.mean(X_scaled, axis=1)
    r, p = pearsonr(ensemble, y)
    results["ensemble_zscore"] = {"r": round(r, 4), "p": round(p, 6)}

    return results


# ========== MAIN ==========

def main():
    db_path = "candle.db"

    print("=" * 80)
    print("ADVANCED FACTOR ANALYSIS")
    print("=" * 80)

    # Load SOL prices and compute forward returns
    sol_prices = load_series(db_path, "sol_ohlcv")
    fwd_returns = compute_forward_returns(sol_prices, days=7)
    print(f"\nSOL prices: {len(sol_prices)} days")
    print(f"Forward returns (7d): {len(fwd_returns)} observations")

    factors_config = {
        "tvl":               {"label": "TVL",                    "modes": ["returns", "level"]},
        "fear_greed":        {"label": "Fear & Greed",           "modes": ["returns", "level"]},
        "dex_volume":        {"label": "DEX Volume",             "modes": ["returns", "level"]},
        "stablecoin_supply": {"label": "Stablecoin Supply",      "modes": ["returns", "level", "delta7"]},
        "vol_regime":        {"label": "Vol Regime",             "modes": ["level"]},
        "chain_fees":        {"label": "Chain Fees",             "modes": ["returns", "level"]},
    }

    lags_to_test = [1, 3, 7, 14]

    # Store aligned data for interaction tests later
    all_aligned = {}
    all_aligned_y = None

    for source, config in factors_config.items():
        raw = load_series(db_path, source)
        if len(raw) < 100:
            print(f"\n{'='*60}")
            print(f"SKIPPING {config['label']} — only {len(raw)} data points")
            continue

        print(f"\n{'='*80}")
        print(f"  {config['label'].upper()} ({source})")
        print(f"  {len(raw)} data points, {min(raw.keys())} to {max(raw.keys())}")
        print(f"{'='*80}")

        # Test each mode
        for mode in config["modes"]:
            if mode == "returns":
                factor_series = compute_returns(raw, days=7)
                mode_label = "% Returns (7d)"
            elif mode == "delta7":
                # 7-day change (not pct)
                sorted_dates = sorted(raw.keys())
                raw_dict = dict(zip(sorted_dates, [raw[d] for d in sorted_dates]))
                factor_series = {}
                for d in sorted_dates:
                    past = d - timedelta(days=7)
                    if past in raw_dict:
                        factor_series[d] = raw[d] - raw_dict[past]
                mode_label = "7d Delta"
            else:
                factor_series = raw
                mode_label = "Raw Level"

            # Find best lag
            best_results = None
            best_lag = 1
            best_abs_r = 0

            for lag in lags_to_test:
                x, y = align_series(factor_series, fwd_returns, lag=lag)
                if len(x) < 50:
                    continue

                p = test_pearson(x, y)
                if p["r"] is not None and abs(p["r"]) > best_abs_r:
                    best_abs_r = abs(p["r"])
                    best_lag = lag

            # Run full analysis at best lag
            x, y = align_series(factor_series, fwd_returns, lag=best_lag)
            if len(x) < 50:
                print(f"\n  [{mode_label}] Too few aligned points ({len(x)})")
                continue

            print(f"\n  --- {mode_label} (best lag: {best_lag}d, n={len(x)}) ---")

            # 1. Pearson
            pearson = test_pearson(x, y)
            print(f"  Pearson:     r={pearson['r']:+.4f}  p={pearson['p']:.6f}  {'***' if pearson['p'] < 0.001 else '**' if pearson['p'] < 0.01 else '*' if pearson['p'] < 0.05 else 'ns'}")

            # 2. Spearman
            spearman = test_spearman(x, y)
            print(f"  Spearman:    rho={spearman['rho']:+.4f}  p={spearman['p']:.6f}  {'***' if spearman['p'] < 0.001 else '**' if spearman['p'] < 0.01 else '*' if spearman['p'] < 0.05 else 'ns'}")

            # 3. Mutual Information
            mi = test_mutual_info(x, y)
            print(f"  Mutual Info: MI={mi['mi']:.4f}" if mi['mi'] is not None else "  Mutual Info: insufficient data")

            # 4. Quantile analysis
            quant = test_quantile_returns(x, y, n_quantiles=5)
            if quant.get("quantile_returns_pct"):
                qr = quant["quantile_returns_pct"]
                q_str = "  ".join(f"{k}:{v:+.2f}%" for k, v in sorted(qr.items()))
                print(f"  Quantiles:   {q_str}")
                print(f"               Spread: {quant['spread_pct']:+.3f}%  KW p={quant['kruskal_wallis_p']:.6f}  {'***' if quant['kruskal_wallis_p'] < 0.001 else '**' if quant['kruskal_wallis_p'] < 0.01 else '*' if quant['kruskal_wallis_p'] < 0.05 else 'ns'}")

            # 5. Log transform
            log_t = test_log_transform(x, y)
            if log_t.get("pearson_log_r") is not None:
                print(f"  Log-Pearson: r={log_t['pearson_log_r']:+.4f}  p={log_t['pearson_log_p']:.6f}")

            # 6. Conditional / regime
            cond = test_conditional(x, y)
            if cond.get("high_regime_r") is not None:
                print(f"  Conditional: high_r={cond['high_regime_r']:+.4f}  low_r={cond['low_regime_r']:+.4f}  diff_p={cond.get('regime_diff_p', 'N/A')}")

            # 7. Granger causality
            granger = test_granger(x, y, max_lag=7)
            if granger.get("granger_f") is not None:
                print(f"  Granger:     F={granger['granger_f']:.4f}  p={granger['granger_p']:.6f}  {'CAUSAL' if granger.get('granger_significant') else 'not causal'}")

            # 8. Rolling stability
            rolling = test_rolling_stability(x, y, window=180)
            if rolling.get("rolling_mean_r") is not None:
                print(f"  Rolling 180d: mean_r={rolling['rolling_mean_r']:+.4f}  std={rolling['rolling_std_r']:.4f}  "
                      f"range=[{rolling['rolling_min_r']:+.4f}, {rolling['rolling_max_r']:+.4f}]  "
                      f"{rolling['pct_windows_significant']:.0f}% windows |r|>0.15")

            # 9. Non-linear transforms
            nonlin = test_nonlinear_transforms(x, y)
            if nonlin:
                print(f"  Squared:     r={nonlin['squared_r']:+.4f}  p={nonlin['squared_p']:.6f}  (U-shape test)")
                print(f"  AbsDev:      r={nonlin['absdev_r']:+.4f}  p={nonlin['absdev_p']:.6f}  (unusual=predictive?)")
                print(f"  Rank:        r={nonlin['rank_r']:+.4f}  p={nonlin['rank_p']:.6f}  (rank-normalized)")

            # Store best mode for interaction analysis
            if mode == "level" or source not in all_aligned:
                all_aligned[source] = x[:min(len(x), len(y))]
                if all_aligned_y is None or len(y) > len(all_aligned_y):
                    all_aligned_y = y[:min(len(x), len(y))]

    # ---------- Multi-factor interaction analysis ----------
    print(f"\n{'='*80}")
    print("  MULTI-FACTOR INTERACTION ANALYSIS")
    print(f"{'='*80}")

    # Need to re-align all factors to the same date range
    # Use the shortest common range
    min_len = min(len(v) for v in all_aligned.values())
    trimmed = {k: v[:min_len] for k, v in all_aligned.items()}
    y_trimmed = all_aligned_y[:min_len] if all_aligned_y is not None else None

    if y_trimmed is not None and len(trimmed) >= 2:
        interactions = test_interactions(trimmed, y_trimmed, np.arange(min_len))

        if interactions.get("interactions"):
            print("\n  Pairwise Interactions (factor1 * factor2 -> returns):")
            for pair, result in sorted(interactions["interactions"].items(), key=lambda x: abs(x[1]["r"]), reverse=True):
                sig = "***" if result["p"] < 0.001 else "**" if result["p"] < 0.01 else "*" if result["p"] < 0.05 else "ns"
                print(f"    {pair:40s} r={result['r']:+.4f}  p={result['p']:.6f}  {sig}")

        if interactions.get("pca"):
            print("\n  PCA Components -> Returns:")
            for pc, result in interactions["pca"].items():
                sig = "***" if result["p"] < 0.001 else "**" if result["p"] < 0.01 else "*" if result["p"] < 0.05 else "ns"
                print(f"    {pc}: r={result['r']:+.4f}  p={result['p']:.6f}  variance={result['variance_explained']:.1%}  {sig}")

        if interactions.get("ensemble_zscore"):
            r = interactions["ensemble_zscore"]["r"]
            p = interactions["ensemble_zscore"]["p"]
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            print(f"\n  Ensemble Z-Score: r={r:+.4f}  p={p:.6f}  {sig}")

    print(f"\n{'='*80}")
    print("  SUMMARY")
    print(f"{'='*80}")
    print("""
  Significance: *** p<0.001  ** p<0.01  * p<0.05  ns=not significant

  KEY QUESTIONS ANSWERED:
  - Pearson/Spearman: Is there a linear/monotonic relationship?
  - Mutual Information: Is there ANY statistical dependency (including non-linear)?
  - Quantile spread: Do extreme factor values predict extreme returns?
  - Conditional: Does the factor work differently in high/low regimes?
  - Granger: Does the factor actually Granger-cause returns?
  - Rolling: Is the signal stable or spurious (lucky time window)?
  - Squared/AbsDev: Does UNUSUALNESS matter regardless of direction?
  - Interactions: Do factor COMBINATIONS predict what individuals can't?
  - PCA: Is there a hidden composite signal across all factors?
    """)


if __name__ == "__main__":
    main()
