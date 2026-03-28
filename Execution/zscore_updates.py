from Execution.config_execution_api import get_position_variables
from Execution.func_price_calls import get_latest_klines, get_latest_mark_price
from Execution.func_stats import calculate_metrics


def get_latest_pair_metrics(ticker_1=False, ticker_2=False):
    if not ticker_1 or not ticker_2:
        config = get_position_variables()
        ticker_1 = config.get("ticker_1")
        ticker_2 = config.get("ticker_2")

    if not ticker_1 or not ticker_2:
        return None

    series_1, series_2 = get_latest_klines(ticker_1, ticker_2)
    if not series_1 or not series_2:
        return None

    latest_price_1 = get_latest_mark_price(ticker_1)
    latest_price_2 = get_latest_mark_price(ticker_2)
    if latest_price_1 is None or latest_price_2 is None:
        return None

    series_1[-1] = latest_price_1
    series_2[-1] = latest_price_2
    metrics = calculate_metrics(series_1, series_2)
    if metrics["latest_zscore"] is None:
        return None

    metrics["ticker_1"] = ticker_1
    metrics["ticker_2"] = ticker_2
    metrics["price_1"] = latest_price_1
    metrics["price_2"] = latest_price_2
    return metrics


def get_latest_zscore(ticker_1=False, ticker_2=False, *_args, called=False):
    metrics = get_latest_pair_metrics(ticker_1, ticker_2)
    if metrics is None:
        return None

    if called:
        return metrics["latest_zscore"]

    print(metrics["latest_zscore"])


if "__main__" == __name__:
    get_latest_zscore()
