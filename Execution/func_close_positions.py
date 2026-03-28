import time

import pybit.exceptions

from Execution.config_execution_api import session_private


def get_position_info(ticker, percent=False):
    side = 0
    size = ""
    liq = ""
    max_retries = 5
    delay = 10

    for attempt in range(max_retries):
        try:
            position = session_private.get_positions(category="linear", symbol=ticker)
            if position.get("retMsg") == "OK":
                size = position["result"]["list"][0]["size"]
                side = position["result"]["list"][0]["side"]
                liq = position["result"]["list"][0]["liqPrice"]

                if percent:
                    try:
                        position_value = float(position["result"]["list"][0]["positionValue"])
                        unrealised_pnl = float(position["result"]["list"][0]["unrealisedPnl"])
                        change_percent = (unrealised_pnl / position_value) * 100 if position_value else 0
                        return side, size, change_percent
                    except (TypeError, ValueError):
                        return 0, 0, 0
            return side, size, liq
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                return 0, 0, 0


def place_market_close_order(ticker, side, size):
    try:
        session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Market",
            qty=size,
            reduceOnly=True,
        )
        print(f"{ticker} Order Closed Successfully!")
    except pybit.exceptions.InvalidRequestError as exc:
        print(exc)
        print(f"Couldn't Close Order: {ticker}")


def place_limit_close_order(ticker, side, size, price):
    try:
        session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Limit",
            qty=size,
            price=price,
            reduceOnly=True,
        )
        print(f"{ticker} Close Order Created!")
    except pybit.exceptions.InvalidRequestError as exc:
        print(exc)
        print(f"Couldn't Close Order: {ticker}")


def flatten_position(ticker):
    side, size, _ = get_position_info(ticker)
    if not side or float(size) <= 0:
        return

    closing_side = "Sell" if side == "Buy" else "Buy"
    place_market_close_order(ticker, closing_side, size)


def close_all_positions(ticker_1, ticker_2, price_1, price_2, direction_1):
    side_1, size_1, _ = get_position_info(ticker_1)
    side_2, size_2, _ = get_position_info(ticker_2)

    if not side_1:
        side_1 = "Buy" if direction_1 == "Long" else "Sell"
    if not side_2:
        side_2 = "Buy" if direction_1 == "Short" else "Sell"

    if float(size_1) > 0:
        place_limit_close_order(ticker_1, side_2, size_1, price_1)

    if float(size_2) > 0:
        place_limit_close_order(ticker_2, side_1, size_2, price_2)

    return 0


def cancel_order(ticker, order_id):
    session_private.cancel_order(category="linear", symbol=ticker, orderId=order_id)


def cancel_all_orders():
    session_private.cancel_all_orders(category="linear", settleCoin="USDT")
