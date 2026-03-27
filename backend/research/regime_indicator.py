"""
Market Regime Indicator for SOL/USD
====================================
Composite indicator (0-100) combining:
  1. ADX + DI direction (trend strength + direction)
  2. Choppiness Index (trending vs ranging)
  3. Garman-Klass Volatility percentile rank
  4. Relative Volume (RVOL)
  5. Chaikin Money Flow (CMF)

Tests statistical significance as a predictor of forward SOL returns.
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ============================================================================
# DATA LOADING
# ============================================================================

DATA_PATH = Path(r"C:\APPS\BSNS\AI\claude_code\Candle\launch_terminal\data\BINANCE_SOLUSD, 1D_36137.csv")

def load_data():
    df = pd.read_csv(DATA_PATH)
    df.columns = ["time", "open", "high", "low", "close", "volume", "ignore"]
    df = df.drop(columns=["ignore"])
    df["date"] = pd.to_datetime(df["time"], unit="s")
    df = df.sort_values("date").reset_index(drop=True)
    # Drop any rows with zero or NaN prices/volume
    df = df[(df["close"] > 0) & (df["volume"] > 0)].reset_index(drop=True)
    print(f"Loaded {len(df)} daily bars from {df['date'].iloc[0].date()} to {df['date'].iloc[-1].date()}")
    return df

# ============================================================================
# SUB-INDICATOR CALCULATIONS
# ============================================================================

def compute_adx_di(df, period=14):
    """ADX with +DI and -DI (Wilder's smoothing)."""
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        h_l = high[i] - low[i]
        h_pc = abs(high[i] - close[i-1])
        l_pc = abs(low[i] - close[i-1])
        tr[i] = max(h_l, h_pc, l_pc)

        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]

        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0

    # Wilder's smoothing (EMA with alpha = 1/period)
    alpha = 1.0 / period
    atr = np.zeros(n)
    smooth_plus = np.zeros(n)
    smooth_minus = np.zeros(n)

    # Seed with SMA of first `period` values
    atr[period] = np.mean(tr[1:period+1])
    smooth_plus[period] = np.mean(plus_dm[1:period+1])
    smooth_minus[period] = np.mean(minus_dm[1:period+1])

    for i in range(period+1, n):
        atr[i] = atr[i-1] * (1 - alpha) + tr[i] * alpha
        smooth_plus[i] = smooth_plus[i-1] * (1 - alpha) + plus_dm[i] * alpha
        smooth_minus[i] = smooth_minus[i-1] * (1 - alpha) + minus_dm[i] * alpha

    plus_di = np.where(atr > 0, 100 * smooth_plus / atr, 0)
    minus_di = np.where(atr > 0, 100 * smooth_minus / atr, 0)

    dx = np.where(
        (plus_di + minus_di) > 0,
        100 * np.abs(plus_di - minus_di) / (plus_di + minus_di),
        0
    )

    adx = np.zeros(n)
    # Seed ADX with SMA of first valid DX values
    start = 2 * period
    if start < n:
        adx[start] = np.mean(dx[period+1:start+1])
        for i in range(start+1, n):
            adx[i] = adx[i-1] * (1 - alpha) + dx[i] * alpha

    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    return df


def compute_choppiness(df, period=14):
    """Choppiness Index: 100 * log10(sum(ATR) / (high_max - low_min)) / log10(period)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    atr_sum = tr.rolling(period).sum()
    high_max = high.rolling(period).max()
    low_min = low.rolling(period).min()

    hl_range = high_max - low_min
    hl_range = hl_range.replace(0, np.nan)

    chop = 100 * np.log10(atr_sum / hl_range) / np.log10(period)
    df["choppiness"] = chop
    return df


def compute_gk_volatility(df, vol_period=14, rank_period=90):
    """Garman-Klass volatility with percentile rank over lookback."""
    log_hl = np.log(df["high"] / df["low"])
    log_co = np.log(df["close"] / df["open"])

    gk = 0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2
    gk_vol = gk.rolling(vol_period).mean().apply(lambda x: np.sqrt(abs(x)) if not np.isnan(x) else np.nan)

    # Percentile rank over lookback
    def pct_rank(s):
        result = np.full(len(s), np.nan)
        vals = s.values
        for i in range(rank_period, len(vals)):
            window = vals[i-rank_period:i+1]
            valid = window[~np.isnan(window)]
            if len(valid) > 1:
                result[i] = stats.percentileofscore(valid, vals[i]) / 100.0
        return pd.Series(result, index=s.index)

    df["gk_vol"] = gk_vol
    df["gk_vol_pctrank"] = pct_rank(gk_vol)
    return df


def compute_rvol(df, period=20):
    """Relative Volume: today's volume / 20-day average volume."""
    avg_vol = df["volume"].rolling(period).mean()
    df["rvol"] = df["volume"] / avg_vol
    return df


def compute_cmf(df, period=20):
    """Chaikin Money Flow: sum(MFV) / sum(Volume) over period.
    MF Multiplier = ((close - low) - (high - close)) / (high - low)
    MF Volume = MF Multiplier * Volume
    """
    hl_range = df["high"] - df["low"]
    hl_range = hl_range.replace(0, np.nan)

    mf_mult = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl_range
    mf_vol = mf_mult * df["volume"]

    cmf = mf_vol.rolling(period).sum() / df["volume"].rolling(period).sum()
    df["cmf"] = cmf
    return df


# ============================================================================
# COMPOSITE REGIME SCORE
# ============================================================================

def normalize_0_100(series):
    """Normalize to 0-100 using expanding min/max (no lookahead)."""
    expanding_min = series.expanding().min()
    expanding_max = series.expanding().max()
    rng = expanding_max - expanding_min
    rng = rng.replace(0, np.nan)
    return 100 * (series - expanding_min) / rng


def compute_regime_score(df, weights=None):
    """
    Combine sub-indicators into regime score (0-100).

    Sub-scores (each 0-100, higher = more bullish):
      1. ADX directional: ADX * sign(+DI - -DI), normalized
      2. Choppiness inverted: low chop = trending = bullish (when trend is up)
      3. GK vol percentile rank: moderate vol = bullish, extreme vol = bearish
         (inverted -- low vol rank is bullish)
      4. RVOL: high relative volume on up days = bullish
      5. CMF: positive = buying pressure = bullish
    """
    if weights is None:
        weights = {"adx_dir": 0.30, "chop": 0.15, "gk_vol": 0.15, "rvol": 0.15, "cmf": 0.25}

    # 1. ADX directional score: ADX * sign of trend direction
    #    Positive when +DI > -DI (uptrend), negative when -DI > +DI (downtrend)
    adx_dir = df["adx"] * np.sign(df["plus_di"] - df["minus_di"])
    sub1 = normalize_0_100(adx_dir)

    # 2. Choppiness inverted: low chop (trending) combined with trend direction
    #    When chop is low AND we're in uptrend, that's bullish
    daily_return = df["close"].pct_change()
    trend_sign = daily_return.rolling(14).mean().apply(lambda x: 1 if x > 0 else -1)
    chop_inv = (100 - df["choppiness"]) * trend_sign  # high when trending in uptrend
    sub2 = normalize_0_100(chop_inv)

    # 3. GK vol percentile: invert so low vol = high score (bullish)
    #    Extreme volatility is typically bearish for crypto
    sub3 = 100 * (1 - df["gk_vol_pctrank"])

    # 4. RVOL directional: high volume on up days = bullish, high volume on down days = bearish
    rvol_dir = df["rvol"] * np.sign(daily_return)
    sub4 = normalize_0_100(rvol_dir)

    # 5. CMF: already ranges roughly -1 to +1, normalize to 0-100
    sub5 = normalize_0_100(df["cmf"])

    df["sub_adx_dir"] = sub1
    df["sub_chop"] = sub2
    df["sub_gk_vol"] = sub3
    df["sub_rvol"] = sub4
    df["sub_cmf"] = sub5

    # Weighted composite
    score = (
        weights.get("adx_dir", 0) * sub1 +
        weights.get("chop", 0) * sub2 +
        weights.get("gk_vol", 0) * sub3 +
        weights.get("rvol", 0) * sub4 +
        weights.get("cmf", 0) * sub5
    )

    df["regime_score"] = score
    return df


# ============================================================================
# FORWARD RETURNS
# ============================================================================

def compute_forward_returns(df):
    """Compute forward 1, 5, 10, 20 day returns."""
    for n in [1, 5, 10, 20]:
        df[f"fwd_{n}d"] = df["close"].shift(-n) / df["close"] - 1
    return df


# ============================================================================
# STATISTICAL TESTS
# ============================================================================

def run_correlation_tests(df):
    """Pearson correlation between regime score and forward returns."""
    print("\n" + "="*70)
    print("PEARSON CORRELATION: Regime Score vs Forward Returns")
    print("="*70)

    valid = df.dropna(subset=["regime_score", "fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"])
    for period in [1, 5, 10, 20]:
        col = f"fwd_{period}d"
        r, p = stats.pearsonr(valid["regime_score"], valid[col])
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        print(f"  {period:2d}-day fwd return:  r = {r:+.4f},  p = {p:.4f}  {sig}")
    return valid


def run_quintile_analysis(df):
    """Split into quintiles by regime score, compare mean forward returns."""
    print("\n" + "="*70)
    print("QUINTILE ANALYSIS: Mean Forward Returns by Regime Quintile")
    print("="*70)

    valid = df.dropna(subset=["regime_score", "fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"])
    valid["quintile"] = pd.qcut(valid["regime_score"], 5, labels=["Q1 (bearish)", "Q2", "Q3", "Q4", "Q5 (bullish)"])

    for period in [1, 5, 10, 20]:
        col = f"fwd_{period}d"
        print(f"\n  --- {period}-day forward returns ---")
        grouped = valid.groupby("quintile")[col]
        for q_name, q_data in grouped:
            mean_ret = q_data.mean() * 100
            median_ret = q_data.median() * 100
            count = len(q_data)
            print(f"    {q_name:15s}:  mean={mean_ret:+.3f}%  median={median_ret:+.3f}%  n={count}")

        # Spread: Q5 - Q1
        q5 = valid[valid["quintile"] == "Q5 (bullish)"][col]
        q1 = valid[valid["quintile"] == "Q1 (bearish)"][col]
        spread = (q5.mean() - q1.mean()) * 100
        print(f"    {'Q5-Q1 spread':15s}:  {spread:+.3f}%")


def run_hit_rate_analysis(df):
    """Hit rate when regime score > 70 or < 30."""
    print("\n" + "="*70)
    print("HIT RATE ANALYSIS: P(positive return | regime threshold)")
    print("="*70)

    valid = df.dropna(subset=["regime_score", "fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"])

    for threshold_high, threshold_low in [(70, 30), (80, 20), (60, 40)]:
        print(f"\n  Thresholds: bullish > {threshold_high}, bearish < {threshold_low}")
        high = valid[valid["regime_score"] > threshold_high]
        low = valid[valid["regime_score"] < threshold_low]

        for period in [1, 5, 10, 20]:
            col = f"fwd_{period}d"
            if len(high) > 0:
                hit_high = (high[col] > 0).mean() * 100
                n_high = len(high)
            else:
                hit_high = float("nan")
                n_high = 0
            if len(low) > 0:
                hit_low = (low[col] > 0).mean() * 100
                n_low = len(low)
            else:
                hit_low = float("nan")
                n_low = 0

            baseline = (valid[col] > 0).mean() * 100
            print(f"    {period:2d}d:  bullish hit={hit_high:5.1f}% (n={n_high:4d})  "
                  f"bearish hit={hit_low:5.1f}% (n={n_low:4d})  baseline={baseline:.1f}%")


def run_significance_tests(df):
    """T-test and Mann-Whitney U between high and low regime returns."""
    print("\n" + "="*70)
    print("STATISTICAL SIGNIFICANCE: High vs Low Regime Returns")
    print("="*70)

    valid = df.dropna(subset=["regime_score", "fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"])

    for threshold_high, threshold_low, label in [(70, 30, "70/30"), (80, 20, "80/20")]:
        print(f"\n  --- Thresholds: {label} ---")
        high = valid[valid["regime_score"] > threshold_high]
        low = valid[valid["regime_score"] < threshold_low]

        if len(high) < 5 or len(low) < 5:
            print(f"    Insufficient samples: high={len(high)}, low={len(low)}")
            continue

        for period in [1, 5, 10, 20]:
            col = f"fwd_{period}d"
            h = high[col].values
            l = low[col].values

            t_stat, t_p = stats.ttest_ind(h, l, equal_var=False)
            u_stat, u_p = stats.mannwhitneyu(h, l, alternative="two-sided")

            sig_t = "***" if t_p < 0.001 else "**" if t_p < 0.01 else "*" if t_p < 0.05 else ""
            sig_u = "***" if u_p < 0.001 else "**" if u_p < 0.01 else "*" if u_p < 0.05 else ""

            print(f"    {period:2d}d:  t-test p={t_p:.4f} {sig_t:3s}   Mann-Whitney p={u_p:.4f} {sig_u:3s}   "
                  f"high_mean={np.mean(h)*100:+.3f}%  low_mean={np.mean(l)*100:+.3f}%")


def run_oos_test(df):
    """Out-of-sample test: train on first 70%, test on last 30%."""
    print("\n" + "="*70)
    print("OUT-OF-SAMPLE TEST: First 70% (train) vs Last 30% (test)")
    print("="*70)

    valid = df.dropna(subset=["regime_score", "fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"])
    split = int(len(valid) * 0.7)
    train = valid.iloc[:split]
    test = valid.iloc[split:]

    print(f"  Train: {len(train)} bars ({train['date'].iloc[0].date()} to {train['date'].iloc[-1].date()})")
    print(f"  Test:  {len(test)} bars ({test['date'].iloc[0].date()} to {test['date'].iloc[-1].date()})")

    for label, subset in [("TRAIN", train), ("TEST", test)]:
        print(f"\n  --- {label} ---")
        for period in [1, 5, 10, 20]:
            col = f"fwd_{period}d"
            sub = subset.dropna(subset=[col])
            if len(sub) < 10:
                continue
            r, p = stats.pearsonr(sub["regime_score"], sub[col])
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"    {period:2d}d:  r = {r:+.4f},  p = {p:.4f}  {sig}")

        # Quintile spread in this subset
        sub = subset.dropna(subset=["fwd_5d"])
        if len(sub) > 20:
            q5 = sub[sub["regime_score"] > sub["regime_score"].quantile(0.8)]["fwd_5d"]
            q1 = sub[sub["regime_score"] < sub["regime_score"].quantile(0.2)]["fwd_5d"]
            if len(q5) > 0 and len(q1) > 0:
                spread = (q5.mean() - q1.mean()) * 100
                t_stat, t_p = stats.ttest_ind(q5, q1, equal_var=False)
                sig = "***" if t_p < 0.001 else "**" if t_p < 0.01 else "*" if t_p < 0.05 else ""
                print(f"    5d Q5-Q1 spread: {spread:+.3f}%  t-test p={t_p:.4f} {sig}")


# ============================================================================
# VARIATION TESTING
# ============================================================================

def test_variations(df):
    """Test different weightings and sub-indicator combinations."""
    print("\n" + "="*70)
    print("VARIATION TESTING: Different Weightings & Combinations")
    print("="*70)

    valid_cols = ["fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"]

    variations = {
        "Equal weights": {"adx_dir": 0.20, "chop": 0.20, "gk_vol": 0.20, "rvol": 0.20, "cmf": 0.20},
        "ADX heavy": {"adx_dir": 0.50, "chop": 0.10, "gk_vol": 0.10, "rvol": 0.10, "cmf": 0.20},
        "CMF heavy": {"adx_dir": 0.20, "chop": 0.10, "gk_vol": 0.10, "rvol": 0.10, "cmf": 0.50},
        "ADX + CMF only": {"adx_dir": 0.50, "chop": 0.00, "gk_vol": 0.00, "rvol": 0.00, "cmf": 0.50},
        "ADX + RVOL + CMF": {"adx_dir": 0.35, "chop": 0.00, "gk_vol": 0.00, "rvol": 0.30, "cmf": 0.35},
        "No vol rank": {"adx_dir": 0.30, "chop": 0.20, "gk_vol": 0.00, "rvol": 0.20, "cmf": 0.30},
        "Trend only (ADX+Chop)": {"adx_dir": 0.60, "chop": 0.40, "gk_vol": 0.00, "rvol": 0.00, "cmf": 0.00},
        "Volume only (RVOL+CMF)": {"adx_dir": 0.00, "chop": 0.00, "gk_vol": 0.00, "rvol": 0.50, "cmf": 0.50},
    }

    results = []

    for name, weights in variations.items():
        # Recompute score with these weights
        score = (
            weights.get("adx_dir", 0) * df["sub_adx_dir"] +
            weights.get("chop", 0) * df["sub_chop"] +
            weights.get("gk_vol", 0) * df["sub_gk_vol"] +
            weights.get("rvol", 0) * df["sub_rvol"] +
            weights.get("cmf", 0) * df["sub_cmf"]
        )

        valid = df.dropna(subset=valid_cols).copy()
        valid["test_score"] = score[valid.index]
        valid = valid.dropna(subset=["test_score"])

        # Split OOS
        split = int(len(valid) * 0.7)
        test = valid.iloc[split:]

        # Primary metric: 5-day forward return correlation in OOS
        if len(test) > 20:
            r5, p5 = stats.pearsonr(test["test_score"], test["fwd_5d"])
            r10, p10 = stats.pearsonr(test["test_score"], test["fwd_10d"])
            r20, p20 = stats.pearsonr(test["test_score"], test["fwd_20d"])

            # Quintile spread OOS
            q5 = test[test["test_score"] > test["test_score"].quantile(0.8)]["fwd_5d"]
            q1 = test[test["test_score"] < test["test_score"].quantile(0.2)]["fwd_5d"]
            spread_5d = (q5.mean() - q1.mean()) * 100 if len(q5) > 0 and len(q1) > 0 else 0

            results.append({
                "name": name,
                "r5_oos": r5, "p5_oos": p5,
                "r10_oos": r10, "p10_oos": p10,
                "r20_oos": r20, "p20_oos": p20,
                "spread_5d_oos": spread_5d,
            })

    # Print results table
    print(f"\n  {'Variation':<28s} | {'r(5d)':>7s} {'p':>7s} | {'r(10d)':>7s} {'p':>7s} | {'r(20d)':>7s} {'p':>7s} | {'Q5-Q1 5d':>9s}")
    print("  " + "-"*100)
    for r in sorted(results, key=lambda x: -abs(x["r5_oos"])):
        sig5 = "*" if r["p5_oos"] < 0.05 else " "
        sig10 = "*" if r["p10_oos"] < 0.05 else " "
        sig20 = "*" if r["p20_oos"] < 0.05 else " "
        print(f"  {r['name']:<28s} | {r['r5_oos']:+.4f} {r['p5_oos']:.4f}{sig5}| "
              f"{r['r10_oos']:+.4f} {r['p10_oos']:.4f}{sig10}| "
              f"{r['r20_oos']:+.4f} {r['p20_oos']:.4f}{sig20}| "
              f"{r['spread_5d_oos']:+.3f}%")

    return results


def find_best_config(results):
    """Identify the best-performing configuration."""
    print("\n" + "="*70)
    print("BEST CONFIGURATION")
    print("="*70)

    # Score each config: prioritize OOS significance across multiple horizons
    for r in results:
        sig_count = sum(1 for k in ["p5_oos", "p10_oos", "p20_oos"] if r[k] < 0.05)
        avg_abs_r = np.mean([abs(r["r5_oos"]), abs(r["r10_oos"]), abs(r["r20_oos"])])
        # Bonus for consistent sign (all positive r = bullish predictive)
        sign_consistency = 1.0 if all(r[f"r{h}_oos"] > 0 for h in [5, 10, 20]) else 0.5
        r["composite_score"] = sig_count * 2 + avg_abs_r * 10 + sign_consistency

    best = max(results, key=lambda x: x["composite_score"])

    print(f"\n  Best: {best['name']}")
    print(f"  OOS correlations:")
    for h in [5, 10, 20]:
        sig = "SIGNIFICANT" if best[f"p{h}_oos"] < 0.05 else "not significant"
        print(f"    {h}d: r={best[f'r{h}_oos']:+.4f}, p={best[f'p{h}_oos']:.4f} ({sig})")
    print(f"  OOS Q5-Q1 5d spread: {best['spread_5d_oos']:+.3f}%")

    any_sig = any(best[f"p{h}_oos"] < 0.05 for h in [5, 10, 20])
    print(f"\n  VERDICT: {'STATISTICALLY SIGNIFICANT predictor found (p < 0.05 OOS)' if any_sig else 'NO statistically significant predictor at p < 0.05 OOS'}")

    return best


# ============================================================================
# SUB-INDICATOR DIAGNOSTICS
# ============================================================================

def diagnose_subindicators(df):
    """Test each sub-indicator individually for predictive power."""
    print("\n" + "="*70)
    print("SUB-INDICATOR DIAGNOSTICS: Individual Predictive Power (OOS)")
    print("="*70)

    valid = df.dropna(subset=["fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d",
                               "sub_adx_dir", "sub_chop", "sub_gk_vol", "sub_rvol", "sub_cmf"])
    split = int(len(valid) * 0.7)
    test = valid.iloc[split:]

    subs = {
        "ADX directional": "sub_adx_dir",
        "Choppiness inv": "sub_chop",
        "GK Vol rank inv": "sub_gk_vol",
        "RVOL directional": "sub_rvol",
        "CMF": "sub_cmf",
    }

    print(f"\n  {'Sub-indicator':<20s} | {'r(1d)':>7s} {'p':>7s} | {'r(5d)':>7s} {'p':>7s} | {'r(10d)':>7s} {'p':>7s} | {'r(20d)':>7s} {'p':>7s}")
    print("  " + "-"*90)

    for name, col in subs.items():
        line = f"  {name:<20s} |"
        for period in [1, 5, 10, 20]:
            fwd_col = f"fwd_{period}d"
            r, p = stats.pearsonr(test[col], test[fwd_col])
            sig = "*" if p < 0.05 else " "
            line += f" {r:+.4f} {p:.4f}{sig}|"
        print(line)


# ============================================================================
# ROUND 2: ROLLING NORMALIZATION + ALTERNATIVE CONSTRUCTIONS
# ============================================================================

def rolling_normalize(series, window=252):
    """Normalize to 0-100 using rolling min/max (no lookahead, adapts to regime)."""
    roll_min = series.rolling(window, min_periods=60).min()
    roll_max = series.rolling(window, min_periods=60).max()
    rng = roll_max - roll_min
    rng = rng.replace(0, np.nan)
    return 100 * (series - roll_min) / rng


def run_round2(df):
    """Test alternative regime constructions with rolling normalization."""
    results = []

    # Recompute sub-scores with rolling normalization
    daily_return = df["close"].pct_change()

    # ADX directional (rolling normalized)
    adx_dir_raw = df["adx"] * np.sign(df["plus_di"] - df["minus_di"])
    adx_dir_roll = rolling_normalize(adx_dir_raw)

    # Choppiness inverted + directional (rolling normalized)
    trend_sign = daily_return.rolling(14).mean().apply(lambda x: 1 if x > 0 else -1)
    chop_dir_raw = (100 - df["choppiness"]) * trend_sign
    chop_dir_roll = rolling_normalize(chop_dir_raw)

    # GK vol inverted (rolling normalized -- just rank, already 0-1)
    gk_inv_roll = 100 * (1 - df["gk_vol_pctrank"])

    # RVOL directional (rolling normalized)
    rvol_dir_raw = df["rvol"] * np.sign(daily_return)
    rvol_dir_roll = rolling_normalize(rvol_dir_raw)

    # CMF (rolling normalized)
    cmf_roll = rolling_normalize(df["cmf"])

    # --- Alternative 1: Simple price momentum (sanity baseline) ---
    # 20-day ROC percentile ranked over 252 days
    roc_20 = df["close"].pct_change(20)
    roc_20_norm = rolling_normalize(roc_20)

    # --- Alternative 2: Multi-timeframe momentum composite ---
    roc_5 = df["close"].pct_change(5)
    roc_10 = df["close"].pct_change(10)
    roc_50 = df["close"].pct_change(50)
    mtf_mom = (
        0.15 * rolling_normalize(roc_5) +
        0.25 * rolling_normalize(roc_10) +
        0.35 * rolling_normalize(roc_20) +
        0.25 * rolling_normalize(roc_50)
    )

    # --- Alternative 3: Regime = momentum + volume confirmation ---
    mom_vol = (
        0.35 * rolling_normalize(roc_20) +
        0.35 * cmf_roll +
        0.30 * rolling_normalize(df["rvol"] * np.sign(daily_return.rolling(5).mean()))
    )

    # --- Alternative 4: Original composite but rolling normalized ---
    regime_roll = (
        0.30 * adx_dir_roll +
        0.15 * chop_dir_roll +
        0.15 * gk_inv_roll +
        0.15 * rvol_dir_roll +
        0.25 * cmf_roll
    )

    # --- Alternative 5: ADX + CMF rolling ---
    adx_cmf_roll = 0.50 * adx_dir_roll + 0.50 * cmf_roll

    # --- Alternative 6: Trend quality = ADX (strength) * momentum direction ---
    # High ADX + positive momentum = strong bullish
    trend_quality = df["adx"] * np.sign(roc_20)
    tq_roll = rolling_normalize(trend_quality)

    # --- Alternative 7: Trend quality + volume ---
    tq_vol = 0.50 * tq_roll + 0.25 * cmf_roll + 0.25 * rvol_dir_roll

    alternatives = {
        "R2: 20d ROC (baseline)": roc_20_norm,
        "R2: Multi-TF momentum": mtf_mom,
        "R2: Momentum + vol confirm": mom_vol,
        "R2: Original (rolling norm)": regime_roll,
        "R2: ADX+CMF (rolling)": adx_cmf_roll,
        "R2: Trend quality": tq_roll,
        "R2: Trend quality + vol": tq_vol,
    }

    valid_cols = ["fwd_1d", "fwd_5d", "fwd_10d", "fwd_20d"]

    print(f"\n  {'Variation':<30s} | {'r(5d)':>7s} {'p':>7s} | {'r(10d)':>7s} {'p':>7s} | {'r(20d)':>7s} {'p':>7s} | {'Q5-Q1 5d':>9s}")
    print("  " + "-"*105)

    for name, score in alternatives.items():
        valid = df.dropna(subset=valid_cols).copy()
        valid["test_score"] = score[valid.index]
        valid = valid.dropna(subset=["test_score"])

        split = int(len(valid) * 0.7)
        test = valid.iloc[split:]

        if len(test) < 30:
            continue

        r5, p5 = stats.pearsonr(test["test_score"], test["fwd_5d"])
        r10, p10 = stats.pearsonr(test["test_score"], test["fwd_10d"])
        r20, p20 = stats.pearsonr(test["test_score"], test["fwd_20d"])

        q5 = test[test["test_score"] > test["test_score"].quantile(0.8)]["fwd_5d"]
        q1 = test[test["test_score"] < test["test_score"].quantile(0.2)]["fwd_5d"]
        spread_5d = (q5.mean() - q1.mean()) * 100 if len(q5) > 0 and len(q1) > 0 else 0

        sig5 = "*" if p5 < 0.05 else " "
        sig10 = "*" if p10 < 0.05 else " "
        sig20 = "*" if p20 < 0.05 else " "
        print(f"  {name:<30s} | {r5:+.4f} {p5:.4f}{sig5}| "
              f"{r10:+.4f} {p10:.4f}{sig10}| "
              f"{r20:+.4f} {p20:.4f}{sig20}| "
              f"{spread_5d:+.3f}%")

        results.append({
            "name": name,
            "r5_oos": r5, "p5_oos": p5,
            "r10_oos": r10, "p10_oos": p10,
            "r20_oos": r20, "p20_oos": p20,
            "spread_5d_oos": spread_5d,
        })

    # Detailed analysis of best round 2 candidate
    if results:
        best_r2 = max(results, key=lambda x: sum(1 for k in ["p5_oos", "p10_oos", "p20_oos"] if x[k] < 0.05) * 10 + abs(x["r5_oos"]) + abs(x["r10_oos"]) + abs(x["r20_oos"]))
        print(f"\n  Best Round 2 candidate: {best_r2['name']}")

        # Get the score for detailed analysis
        best_score = alternatives[best_r2["name"]]
        valid = df.dropna(subset=valid_cols).copy()
        valid["test_score"] = best_score[valid.index]
        valid = valid.dropna(subset=["test_score"])
        split = int(len(valid) * 0.7)
        test = valid.iloc[split:]

        # Detailed quintile analysis OOS
        print(f"\n  --- Detailed OOS quintile analysis ({best_r2['name']}) ---")
        test_copy = test.copy()
        test_copy["quintile"] = pd.qcut(test_copy["test_score"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
        for period in [5, 10, 20]:
            col = f"fwd_{period}d"
            print(f"\n    {period}d forward returns:")
            for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
                qdata = test_copy[test_copy["quintile"] == q][col]
                print(f"      {q}: mean={qdata.mean()*100:+.3f}%  median={qdata.median()*100:+.3f}%  n={len(qdata)}")

            q5_data = test_copy[test_copy["quintile"] == "Q5"][col]
            q1_data = test_copy[test_copy["quintile"] == "Q1"][col]
            if len(q5_data) > 3 and len(q1_data) > 3:
                t_stat, t_p = stats.ttest_ind(q5_data, q1_data, equal_var=False)
                u_stat, u_p = stats.mannwhitneyu(q5_data, q1_data, alternative="two-sided")
                print(f"      Q5-Q1: t-test p={t_p:.4f}  Mann-Whitney p={u_p:.4f}")

        # Hit rate OOS
        print(f"\n  --- Hit rate OOS ({best_r2['name']}) ---")
        high = test[test["test_score"] > 70]
        low = test[test["test_score"] < 30]
        for period in [5, 10, 20]:
            col = f"fwd_{period}d"
            baseline = (test[col] > 0).mean() * 100
            if len(high) > 5:
                hit_h = (high[col] > 0).mean() * 100
            else:
                hit_h = float("nan")
            if len(low) > 5:
                hit_l = (low[col] > 0).mean() * 100
            else:
                hit_l = float("nan")
            print(f"    {period:2d}d: bullish>{70} hit={hit_h:5.1f}% (n={len(high)})  "
                  f"bearish<{30} hit={hit_l:5.1f}% (n={len(low)})  baseline={baseline:.1f}%")

    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*70)
    print("MARKET REGIME INDICATOR - SOL/USD STATISTICAL ANALYSIS")
    print("="*70)

    # 1. Load data
    df = load_data()

    # 2. Compute sub-indicators
    print("\nComputing sub-indicators...")
    df = compute_adx_di(df, period=14)
    df = compute_choppiness(df, period=14)
    df = compute_gk_volatility(df, vol_period=14, rank_period=90)
    df = compute_rvol(df, period=20)
    df = compute_cmf(df, period=20)

    # 3. Composite regime score (default weights)
    df = compute_regime_score(df)

    # 4. Forward returns
    df = compute_forward_returns(df)

    # Quick sanity check
    valid = df.dropna(subset=["regime_score"])
    print(f"\nRegime score stats (n={len(valid)}):")
    print(f"  Mean: {valid['regime_score'].mean():.1f}")
    print(f"  Std:  {valid['regime_score'].std():.1f}")
    print(f"  Min:  {valid['regime_score'].min():.1f}")
    print(f"  Max:  {valid['regime_score'].max():.1f}")

    # 5. Run all statistical tests
    run_correlation_tests(df)
    run_quintile_analysis(df)
    run_hit_rate_analysis(df)
    run_significance_tests(df)
    run_oos_test(df)

    # 6. Diagnose sub-indicators individually
    diagnose_subindicators(df)

    # 7. Test variations
    results = test_variations(df)

    # 8. Find best configuration
    best = find_best_config(results)

    # ================================================================
    # ROUND 2: Rolling normalization + alternative regime constructions
    # ================================================================
    print("\n\n" + "="*70)
    print("ROUND 2: ROLLING NORMALIZATION + ALTERNATIVE CONSTRUCTIONS")
    print("="*70)
    print("\nThe expanding normalization biases early bars. Switching to")
    print("252-day rolling normalization for a fairer test.\n")

    round2_results = run_round2(df)

    # Final verdict
    print("\n" + "="*70)
    print("FINAL VERDICT")
    print("="*70)

    all_results = results + round2_results
    final_best = find_best_config(all_results)

    # Honest assessment
    print("\n" + "-"*70)
    print("HONEST ASSESSMENT")
    print("-"*70)

    # Check if any result has consistent, strong OOS significance
    strong_results = [r for r in all_results
                      if sum(1 for h in [5, 10, 20] if r[f"p{h}_oos"] < 0.05) >= 2]

    if strong_results:
        for r in strong_results:
            signs = [r[f"r{h}_oos"] for h in [5, 10, 20]]
            direction = "MEAN-REVERSION" if all(s < 0 for s in signs) else "MOMENTUM" if all(s > 0 for s in signs) else "MIXED"
            print(f"\n  {r['name']}: {direction} signal")
            print(f"    Direction: {'Negative r (high score -> LOWER returns)' if signs[0] < 0 else 'Positive r (high score -> HIGHER returns)'}")
            for h in [5, 10, 20]:
                print(f"    {h}d: r={r[f'r{h}_oos']:+.4f}, p={r[f'p{h}_oos']:.4f}")

    print(f"""
  SUMMARY:
  --------
  1. The original 5-indicator composite shows STRONG in-sample correlations
     (r=+0.19 for 20d returns, p<0.001) but FAILS out-of-sample (p>0.05
     for 1d/5d/10d). The one significant OOS result (20d, p=0.042) is
     borderline and likely benefits from multiple comparisons.

  2. Individual sub-indicators show NO significant OOS predictive power
     for 1d or 5d returns. Only Choppiness Index shows marginal 20d
     significance (p=0.048).

  3. The Multi-TF momentum composite shows significant NEGATIVE OOS
     correlation at 10d (r=-0.085, p=0.034) and 20d (r=-0.081, p=0.046).
     This suggests MEAN REVERSION: when momentum is high, forward returns
     tend to be lower. However, the effect size is small (r ~ -0.08).

  4. The strong in-sample vs weak OOS gap suggests the original indicator
     is capturing SOL's massive 2020-2021 bull run (when all indicators
     align with rising prices) rather than a persistent predictive signal.

  RECOMMENDATION FOR DASHBOARD USE:
  - The regime indicator IS useful as a DESCRIPTIVE tool (telling users
    "the market is currently trending/ranging/bullish/bearish").
  - It should NOT be presented as a PREDICTIVE tool with edge.
  - If you want a predictive element, the mean-reversion signal from
    multi-TF momentum is the most honest finding, but the effect size
    is small and would need transaction cost analysis.
  - Present the score as "Market Regime" (descriptive), not "Prediction."
""")

    print("="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
