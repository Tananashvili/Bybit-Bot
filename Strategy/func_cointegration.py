import math

import pandas as pd

from Strategy.config_strategy_api import z_score_window
from pair_stats import build_spread, calculate_pair_metrics, calculate_zscore_series


def calculate_zscore(spread):
    zscores = calculate_zscore_series(spread, z_score_window)
    if zscores.empty:
        return {
            "z_scores": [],
            "z_min": 0.0,
            "z_max": 0.0,
            "close_to_min_count": 0,
            "close_to_max_count": 0,
        }

    z_min = float(zscores.min())
    z_max = float(zscores.max())
    return {
        "z_scores": zscores.tolist(),
        "z_min": z_min,
        "z_max": z_max,
        "close_to_min_count": 0,
        "close_to_max_count": 0,
    }


def calculate_spread(series_1, series_2, hedge_ratio, intercept=0.0):
    return build_spread(series_1, series_2, hedge_ratio, intercept)


def calculate_cointegration(series_1, series_2):
    metrics = calculate_pair_metrics(series_1, series_2, z_score_window)
    return (
        metrics["coint_flag"],
        round(metrics["p_value"], 4),
        round(metrics["t_value"], 4),
        round(metrics["critical_value"], 4),
        metrics["hedge_ratio"],
        metrics["zero_crossings"],
        metrics["intercept"],
        metrics["half_life"],
    )


def extract_close_prices(prices):
    close_prices = []
    for price_values in prices:
        close_price = float(price_values)
        if math.isnan(close_price):
            return []
        close_prices.append(close_price)
    return close_prices


def get_cointegrated_pairs(prices, bad_pairs):
    coint_pair_list = []
    included_list = set()

    for sym_1 in prices.keys():
        for sym_2 in prices.keys():
            if sym_2 == sym_1:
                continue

            unique_pair = tuple(sorted((sym_1, sym_2)))
            if unique_pair in included_list:
                continue

            series_1 = extract_close_prices(prices[sym_1])
            series_2 = extract_close_prices(prices[sym_2])
            metrics = calculate_pair_metrics(series_1, series_2, z_score_window)

            if metrics["coint_flag"] != 1 or metrics["latest_zscore"] is None:
                continue

            included_list.add(unique_pair)
            coint_pair_list.append(
                {
                    "sym_1": sym_1,
                    "sym_2": sym_2,
                    "p_value": round(metrics["p_value"], 4),
                    "t_value": round(metrics["t_value"], 4),
                    "c_value": round(metrics["critical_value"], 4),
                    "hedge_ratio": metrics["hedge_ratio"],
                    "intercept": metrics["intercept"],
                    "zero_crossings": metrics["zero_crossings"],
                    "half_life": metrics["half_life"],
                    "z_score": metrics["latest_zscore"],
                    "abs": abs(metrics["latest_zscore"]),
                }
            )

    df_coint = pd.DataFrame(coint_pair_list)
    if df_coint.empty:
        return df_coint

    df_coint = df_coint[
        ~df_coint["sym_1"].isin(bad_pairs) & ~df_coint["sym_2"].isin(bad_pairs)
    ]
    return df_coint
