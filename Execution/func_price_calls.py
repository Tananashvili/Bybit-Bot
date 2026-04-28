import time

from pybit.exceptions import FailedRequestError
from requests.exceptions import RequestException

from Execution.config_execution_api import kline_limit, session_public, timeframe
from Execution.func_calcultions import extract_close_prices


def get_ticker_snapshot(ticker):
    try:
        response = session_public.get_tickers(category="linear", symbol=ticker)
        ticker_list = response.get("result", {}).get("list", [])
        return ticker_list[0] if ticker_list else {}
    except (FailedRequestError, RequestException, TimeoutError) as exc:
        print(f"[warn] ticker snapshot failed for {ticker}: {exc}")
        return {}


def get_latest_mark_price(ticker):
    snapshot = get_ticker_snapshot(ticker)
    try:
        return float(snapshot["markPrice"])
    except (KeyError, TypeError, ValueError):
        return None


def get_price_klines(ticker):
    for attempt in range(3):
        try:
            prices = session_public.get_mark_price_kline(
                category="linear",
                symbol=ticker,
                interval=timeframe,
                limit=kline_limit,
            )

            time.sleep(0.1)
            kline_list = prices.get("result", {}).get("list", [])
            if len(kline_list) != kline_limit:
                return []

            return kline_list
        except (FailedRequestError, RequestException, TimeoutError) as exc:
            if attempt < 2:
                print(
                    f"[warn] kline fetch failed for {ticker} "
                    f"(attempt {attempt + 1}/3): {exc}"
                )
                time.sleep(5)
            else:
                print(f"[warn] giving up on kline fetch for {ticker}: {exc}")
                return []


def get_latest_klines(ticker_1, ticker_2):
    series_1 = []
    series_2 = []
    prices_1 = get_price_klines(ticker_1)
    prices_2 = get_price_klines(ticker_2)

    if prices_1:
        series_1 = extract_close_prices(prices_1)
        series_1.reverse()
    if prices_2:
        series_2 = extract_close_prices(prices_2)
        series_2.reverse()

    return series_1, series_2
