from config_execution_api import session_private, limit_order_basis
from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details


def place_order(ticker, price, quantity, direction, stop_loss):

    # Set variables
    if direction == "Long":
        side = "Buy"
    else:
        side = "Sell"

    # Place limit order
    if limit_order_basis:
        order = session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Limit",
            qty=quantity,
            price=price,
            timeInForce="PostOnly",
            orderFilter="tpslOrder",
            stopLoss=stop_loss
        )
    else:
        order = session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Market",
            qty=quantity,
            timeInForce="PostOnly",
        )

    # Return order
    return order

ticker = 'BTCUSDT'
direction = 'Long'

orderbook = get_orderbook_info(ticker)
mid_price, _, _, = get_trade_details(ticker, orderbook, direction, 0)


place_order(ticker, mid_price, )