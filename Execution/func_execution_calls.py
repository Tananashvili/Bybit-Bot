from config_execution_api import session_private, limit_order_basis, leverage
from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details
from pybit.exceptions import InvalidRequestError

# Set leverage
def set_leverage(ticker):

    # Set Isolated Mode
    session_private.set_margin_mode(
        setMarginMode="ISOLATED_MARGIN",
    )

    # Setting the leverage
    try:
        session_private.set_leverage(
            category="linear",
            symbol=ticker,
            buyLeverage=leverage,
            sellLeverage=leverage,
        )
    except InvalidRequestError:
        pass

    # Return
    return


# Place limit or market order
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

place_order('BTCUSDT', '79,814.60', )

# Initialise execution
def initialise_order_execution(ticker, direction, capital):
    orderbook = get_orderbook_info(ticker)
    if orderbook:
        mid_price, stop_loss, quantity = get_trade_details(orderbook, direction, capital)
        if quantity > 0:
            order = place_order(ticker, mid_price, quantity, direction, stop_loss)
            if "result" in order.keys():
                if "orderId" in order["result"]:
                    return order["result"]["orderId"]
    return 0
