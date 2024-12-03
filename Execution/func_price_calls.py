from config_execution_api import session_public, timeframe, kline_limit
from func_calcultions import extract_close_prices
from pybit.exceptions import FailedRequestError
import datetime
import time


# Get trade liquidity for ticker
def get_ticker_trade_liquidity(ticker):

    # Get trades history
    trades = session_public.get_orderbook(
        category="linear",
        symbol=ticker,
        limit=25
    )

    # Get the list for calculating the average liquidity
    quantity_list = []
    if "result" in trades.keys():
        for bids in trades["result"]["b"]:
            quantity_list.append(float(bids[1]))
        for asks in trades["result"]["a"]:
            quantity_list.append(float(asks[1]))

    # Return output
    if len(quantity_list) > 0:
        avg_liq = sum(quantity_list) / len(quantity_list)
        res_trades_price = float(trades["result"]["a"][0][0])
        return (avg_liq, res_trades_price)
    return (0, 0)


# Get start times
def get_timestamps():
    time_start_date = 0
    time_next_date = 0
    now = datetime.datetime.now()
    if timeframe == 60:
        time_start_date = now - datetime.timedelta(hours=kline_limit)
        time_next_date = now + datetime.timedelta(seconds=30)
    if timeframe == "D":
        time_start_date = now - datetime.timedelta(days=kline_limit)
        time_next_date = now + datetime.timedelta(minutes=1)
    time_start_seconds = int(time_start_date.timestamp())
    time_now_seconds = int(now.timestamp())
    time_next_seconds = int(time_next_date.timestamp())
    return (time_start_seconds, time_now_seconds, time_next_seconds)


# Get historical prices (klines)
def get_price_klines(ticker):

    # Get prices
    # time_start_seconds, _, _ = get_timestamps()
    for attempt in range(3):
        try:
            prices = session_public.get_mark_price_kline(
                category="linear",
                symbol=ticker,
                interval=timeframe,
                # start=time_start_seconds,          # ეს რო ამოვაგდე სწორად წამოიღო ფასები და არ ვიცი რამდენად საჭიროა ???
                limit=kline_limit,
            )

            # Return prices output
            time.sleep(0.1)
            if len(prices["result"]["list"]) != kline_limit:
                return []
            return prices["result"]["list"]
        
        except FailedRequestError as e:
            if attempt < 3:
                time.sleep(5)
            else:
                raise    


# Get latest klines
def get_latest_klines(ticker_1, ticker_2):
    series_1 = []
    series_2 = []
    prices_1 = get_price_klines(ticker_1)
    prices_2 = get_price_klines(ticker_2)

    if len(prices_1) > 0:
        series_1 = extract_close_prices(prices_1)
    if len(prices_2) > 0:
        series_2 = extract_close_prices(prices_2)
    return (series_1, series_2)
