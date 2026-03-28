from Execution.config_execution_api import z_score_window
from pair_stats import build_spread, calculate_pair_metrics, calculate_zscore_series


def calculate_zscore(spread):
    zscores = calculate_zscore_series(spread, z_score_window)
    return {
        "z_scores": zscores.tolist(),
        "z_min": float(zscores.min()) if not zscores.empty else 0.0,
        "z_max": float(zscores.max()) if not zscores.empty else 0.0,
        "close_to_min_count": 0,
        "close_to_max_count": 0,
    }


def calculate_spread(series_1, series_2, hedge_ratio, intercept=0.0):
    return build_spread(series_1, series_2, hedge_ratio, intercept)


def calculate_metrics(series_1, series_2):
    return calculate_pair_metrics(series_1, series_2, z_score_window)
