import math

import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint


def build_spread(series_1, series_2, hedge_ratio, intercept=0.0):
    return pd.Series(series_1, dtype="float64") - (
        intercept + pd.Series(series_2, dtype="float64") * hedge_ratio
    )


def calculate_zscore_series(spread, window):
    df = pd.DataFrame({"spread": pd.Series(spread, dtype="float64")})
    rolling_mean = df["spread"].rolling(window=window, min_periods=window).mean()
    rolling_std = df["spread"].rolling(window=window, min_periods=window).std()
    zscores = ((df["spread"] - rolling_mean) / rolling_std).dropna()
    return zscores.astype("float64")


def estimate_half_life(spread):
    spread_series = pd.Series(spread, dtype="float64").dropna()
    lagged = spread_series.shift(1)
    delta = spread_series - lagged
    regression_frame = pd.DataFrame({"lagged": lagged, "delta": delta}).dropna()

    if regression_frame.empty:
        return math.inf

    model = sm.OLS(
        regression_frame["delta"],
        sm.add_constant(regression_frame["lagged"], has_constant="add"),
    ).fit()

    beta = float(model.params.iloc[1])
    if beta >= 0:
        return math.inf

    half_life = -math.log(2) / beta
    return float(half_life) if half_life > 0 else math.inf


def calculate_pair_metrics(series_1, series_2, zscore_window):
    default_result = {
        "coint_flag": 0,
        "p_value": 1.0,
        "t_value": 0.0,
        "critical_value": 0.0,
        "hedge_ratio": 0.0,
        "intercept": 0.0,
        "spread": [],
        "zscore_list": [],
        "latest_zscore": None,
        "zero_crossings": 0,
        "half_life": math.inf,
    }

    if len(series_1) != len(series_2) or len(series_1) < zscore_window + 5:
        return default_result

    try:
        y = pd.Series(series_1, dtype="float64")
        x = pd.Series(series_2, dtype="float64")
        regression_model = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
        intercept = float(regression_model.params.iloc[0])
        hedge_ratio = float(regression_model.params.iloc[1])

        spread = build_spread(y, x, hedge_ratio, intercept)
        zscore_list = calculate_zscore_series(spread, zscore_window)
        if zscore_list.empty:
            return default_result

        coint_res = coint(y, x, trend="c")
        t_value = float(coint_res[0])
        p_value = float(coint_res[1])
        critical_value = float(coint_res[2][1])
        zero_crossings = int(((spread.shift(1) * spread) < 0).sum())
        half_life = estimate_half_life(spread)

        result = {
            "coint_flag": int(p_value < 0.05 and t_value < critical_value),
            "p_value": p_value,
            "t_value": t_value,
            "critical_value": critical_value,
            "hedge_ratio": hedge_ratio,
            "intercept": intercept,
            "spread": spread.tolist(),
            "zscore_list": zscore_list.tolist(),
            "latest_zscore": float(zscore_list.iloc[-1]),
            "zero_crossings": zero_crossings,
            "half_life": half_life,
        }
        return result
    except Exception:
        return default_result
