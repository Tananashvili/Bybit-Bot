from Execution.config_execution_api import get_position_variables
from Execution.func_calcultions import extract_close_prices
from Execution.func_price_calls import get_latest_mark_price, get_price_klines
from Execution.func_stats import calculate_metrics


def get_price_series(ticker, use_live_mark=True):
    raw_klines = get_price_klines(ticker)
    if not raw_klines:
        return [], None

    series = extract_close_prices(raw_klines)
    if not series:
        return [], None

    series.reverse()
    if len(series) < 2:
        return [], None

    if use_live_mark:
        latest_price = get_latest_mark_price(ticker)
        if latest_price is None:
            return [], None
        series[-1] = latest_price
        return series, latest_price

    closed_series = series[:-1]
    if not closed_series:
        return [], None
    return closed_series, closed_series[-1]


def get_latest_pair_metrics(ticker_1=False, ticker_2=False, use_live_mark=True):
    if not ticker_1 or not ticker_2:
        config = get_position_variables()
        ticker_1 = config.get("ticker_1")
        ticker_2 = config.get("ticker_2")

    if not ticker_1 or not ticker_2:
        return None

    series_1, latest_price_1 = get_price_series(ticker_1, use_live_mark=use_live_mark)
    series_2, latest_price_2 = get_price_series(ticker_2, use_live_mark=use_live_mark)
    if not series_1 or not series_2:
        return None

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
