from Strategy.config_strategy_api import (
    max_spread_bps,
    min_turnover_24h,
    session_public,
)


def get_all_linear_instruments():
    all_symbols = []
    cursor = None

    while True:
        request_args = {
            "category": "linear",
            "limit": 1000,
        }
        if cursor:
            request_args["cursor"] = cursor

        response = session_public.get_instruments_info(**request_args)
        symbol_list = response.get("result", {}).get("list", [])
        all_symbols.extend(symbol_list)

        cursor = response.get("result", {}).get("nextPageCursor")
        if not cursor:
            break

    return all_symbols


def get_ticker_snapshot_map():
    response = session_public.get_tickers(category="linear")
    ticker_list = response.get("result", {}).get("list", [])
    return {item["symbol"]: item for item in ticker_list}


def get_tradeable_symbols():
    tickers_by_symbol = get_ticker_snapshot_map()
    instruments = get_all_linear_instruments()

    tradeable = []
    for symbol in instruments:
        if symbol.get("quoteCoin") != "USDT" or symbol.get("status") != "Trading":
            continue

        ticker_data = tickers_by_symbol.get(symbol["symbol"])
        if not ticker_data:
            continue

        try:
            turnover_24h = float(ticker_data["turnover24h"])
            bid_price = float(ticker_data["bid1Price"])
            ask_price = float(ticker_data["ask1Price"])
            mark_price = float(ticker_data["markPrice"])
        except (KeyError, TypeError, ValueError):
            continue

        if turnover_24h < min_turnover_24h or min(bid_price, ask_price, mark_price) <= 0:
            continue

        spread_bps = ((ask_price - bid_price) / mark_price) * 10000
        if spread_bps > max_spread_bps:
            continue

        tradeable.append(
            {
                **symbol,
                "turnover24h": turnover_24h,
                "spread_bps": spread_bps,
                "markPrice": mark_price,
            }
        )

    return tradeable
