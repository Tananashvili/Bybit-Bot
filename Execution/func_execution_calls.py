from pybit.exceptions import InvalidRequestError

from Execution.config_execution_api import (
    limit_order_basis,
    session_private,
    session_public,
)
from Execution.config_ws_connect import get_orderbook_info
from Execution.helping_functions import round_quantity
from Execution.func_calcultions import get_trade_details


def set_leverage(ticker, x):
    session_private.set_margin_mode(setMarginMode="ISOLATED_MARGIN")

    try:
        session_private.set_leverage(
            category="linear",
            symbol=ticker,
            buyLeverage=x,
            sellLeverage=x,
        )
    except InvalidRequestError:
        pass


def place_order(ticker, price, quantity, direction):
    side = "Buy" if direction == "Long" else "Sell"

    if limit_order_basis:
        return session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Limit",
            qty=quantity,
            price=price,
        )

    return session_private.place_order(
        category="linear",
        symbol=ticker,
        side=side,
        orderType="Market",
        qty=quantity,
    )


def check_order_status(ticker, order_id=None):
    open_order_args = {
        "category": "linear",
        "symbol": ticker,
    }
    if order_id:
        open_order_args["orderId"] = order_id

    open_orders = session_private.get_open_orders(**open_order_args)
    open_order_list = open_orders.get("result", {}).get("list", [])
    if open_order_list:
        order_details = open_order_list[0]
        order_status = order_details.get("orderStatus", "Unknown")
        left_qty = float(order_details.get("leavesQty", 0) or 0)
        return order_status, left_qty

    if not order_id:
        return "Unknown", 0

    try:
        history = session_private.get_order_history(
            category="linear",
            symbol=ticker,
            orderId=order_id,
        )
        history_list = history.get("result", {}).get("list", [])
        if history_list:
            order_details = history_list[0]
            order_status = order_details.get("orderStatus", "Unknown")
            left_qty = float(order_details.get("leavesQty", 0) or 0)
            return order_status, left_qty
    except Exception:
        pass

    return "Unknown", 0


def get_wallet_balance():
    balance = session_private.get_wallet_balance(
        accountType="UNIFIED",
        coin="USDT",
    )
    return float(balance["result"]["list"][0]["coin"][0]["walletBalance"])


def get_max_leverage(ticker_1, ticker_2):
    risk_limit_1 = session_private.get_risk_limit(
        category="linear",
        symbol=ticker_1,
    )
    risk_limit_2 = session_private.get_risk_limit(
        category="linear",
        symbol=ticker_2,
    )
    max_leverage_1 = risk_limit_1["result"]["list"][0]["maxLeverage"]
    max_leverage_2 = risk_limit_2["result"]["list"][0]["maxLeverage"]
    return min(float(max_leverage_1), float(max_leverage_2))


def get_instrument_meta(ticker):
    info = session_public.get_instruments_info(category="linear", symbol=ticker)
    meta = info.get("result", {}).get("list", [])
    return meta[0] if meta else {}


def initialise_order_execution(ticker, direction, leverage, qty=False, size=False):
    ticker_info = get_instrument_meta(ticker)
    qty_step = float(ticker_info["lotSizeFilter"]["qtyStep"])
    direction_reverse = "Short" if direction == "Long" else "Long"

    orderbook = get_orderbook_info(ticker)
    mid_price = get_trade_details(orderbook, direction_reverse)

    if qty:
        quantity = round_quantity(float(qty), qty_step)
    else:
        quantity = (size * 0.97 * float(leverage)) / float(mid_price)
        quantity = round_quantity(quantity, qty_step)

    set_leverage(ticker, leverage)
    try:
        order = place_order(ticker, mid_price, quantity, direction)
    except InvalidRequestError:
        quantity = round_quantity(float(quantity) * 0.97, qty_step)
        order = place_order(ticker, mid_price, quantity, direction)

    if "result" in order and "orderId" in order["result"]:
        return order["result"]["orderId"]
    return None


def set_tpsl(ticker, sl_price):
    try:
        session_private.set_trading_stop(
            category="linear",
            symbol=ticker,
            tpslMode="Full",
            stopLoss=sl_price,
            positionIdx=0,
        )
    except InvalidRequestError:
        pass
