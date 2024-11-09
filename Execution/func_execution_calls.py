from config_execution_api import session_private, session_public, limit_order_basis, leverage, capital
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
def place_order(ticker, price, quantity, direction):

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


# Check whether order is filled or not
def check_order_status(ticker):

    order= session_private.get_open_orders(
        category="linear",
        symbol=ticker,
    )

    try:
        order_status = order['result']['list'][0]['orderStatus']
        return order_status
    
    except IndexError:
        return 'Filled'


# Initialise execution
def initialise_order_execution(ticker, direction):
    direction_reverse = 'Short' if direction == 'Long' else 'Long'

    ticker_info = session_public.get_instruments_info(
        category='linear',
        symbol=ticker
    )
    qty_step = ticker_info['result']['list'][0]['lotSizeFilter']['qtyStep']

    orderbook = get_orderbook_info(ticker)
    mid_price= get_trade_details(orderbook, direction_reverse)
    quantity = (capital * leverage) / (2 * mid_price)
    quantity = round(quantity / float(qty_step)) * float(qty_step)

    set_leverage(ticker, str(leverage))
    order = place_order(ticker, mid_price, quantity, direction)

    if "result" in order.keys():
        if "orderId" in order["result"]:
            return order["result"]["orderId"]
            


def set_tpsl(ticker, sl_price):
    try:
        session_private.set_trading_stop(
            category='linear',
            symbol=ticker,
            tpslMode='Full',
            stopLoss=sl_price,
            positionIdx=0
        )
    except InvalidRequestError:
        pass