from Strategy.config_strategy_api import kline_limit, session_public, timeframe
import time


def get_price_klines(symbol):
    prices = session_public.get_mark_price_kline(
        category="linear",
        symbol=symbol,
        interval=timeframe,
        limit=kline_limit,
    )

    time.sleep(0.1)

    kline_list = prices.get("result", {}).get("list", [])
    if len(kline_list) != kline_limit:
        return []

    return kline_list
