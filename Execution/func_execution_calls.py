from Execution.config_execution_api import session_private, session_public, limit_order_basis, get_position_variables
from Execution.config_ws_connect import get_orderbook_info
from Execution.helping_functions import round_quantity
from Execution.func_calcultions import get_trade_details
from pybit.exceptions import InvalidRequestError


# Set leverage
def set_leverage(ticker):

    config = get_position_variables()
    leverage = config['leverage']

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
        if order_status == 'PartiallyFilled':
            left_qty = order['result']['list'][0]['leavesQty']
        else:
            left_qty = False
        return order_status, left_qty
    
    except IndexError:
        return 'Filled', False


# Initialise execution
def initialise_order_execution(ticker, direction, qty=False):

    config = get_position_variables()
    leverage = config['leverage']
    capital = config['capital']
    direction_reverse = 'Short' if direction == 'Long' else 'Long'

    ticker_info = session_public.get_instruments_info(
        category='linear',
        symbol=ticker
    )
    qty_step = ticker_info['result']['list'][0]['lotSizeFilter']['qtyStep']

    orderbook = get_orderbook_info(ticker)
    mid_price= get_trade_details(orderbook, direction_reverse)

    if qty:
        quantity = qty
    else:
        quantity = (capital * float(leverage)) / (2 * float(mid_price))
        quantity = round_quantity(quantity, float(qty_step))

    set_leverage(ticker)
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


def get_wallet_balance():
    balance = session_private.get_wallet_balance(
        accountType="UNIFIED",
        coin="USDT",
    )

    return float(balance['result']['list'][0]['coin'][0]['availableToWithdraw'])