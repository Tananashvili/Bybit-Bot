from Execution.config_execution_api import session_private, session_public, limit_order_basis, get_position_variables
from Execution.config_ws_connect import get_orderbook_info
from Execution.helping_functions import round_quantity
from Execution.func_calcultions import get_trade_details
from pybit.exceptions import InvalidRequestError


# Set leverage
def set_leverage(ticker, x):

    session_private.set_margin_mode(
        setMarginMode="ISOLATED_MARGIN",
    )

    try:
        session_private.set_leverage(
            category="linear",
            symbol=ticker,
            buyLeverage=x,
            sellLeverage=x,
        )
    except InvalidRequestError:
        pass

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
        if order_status == 'PartiallyFilled' or order_status == 'New':
            left_qty = order['result']['list'][0]['leavesQty']
        else:
            left_qty = 0
        return order_status, left_qty
    
    except IndexError:
        return 'Filled', 0
    

def get_wallet_balance():
    balance = session_private.get_wallet_balance(
        accountType="UNIFIED",
        coin="USDT",
    )

    return float(balance['result']['list'][0]['coin'][0]['walletBalance'])


def get_max_leverage(ticker_1, ticker_2):
    risk_limit_1 = session_private.get_risk_limit(
        category="linear",
        symbol=ticker_1,
    )

    risk_limit_2 = session_private.get_risk_limit(
        category="linear",
        symbol=ticker_2,
    )
    max_leverage_1 = risk_limit_1['result']['list'][0]['maxLeverage']
    max_leverage_2 = risk_limit_2['result']['list'][0]['maxLeverage']

    return min(float(max_leverage_1), float(max_leverage_2))


# Initialise execution
def initialise_order_execution(ticker, direction, leverage, qty=False, first_order=True, size=False):

    ticker_info = session_public.get_instruments_info(
        category='linear',
        symbol=ticker
    )
    qty_step = ticker_info['result']['list'][0]['lotSizeFilter']['qtyStep']
    direction_reverse = 'Short' if direction == 'Long' else 'Long'

    orderbook = get_orderbook_info(ticker)
    mid_price= get_trade_details(orderbook, direction_reverse)

    if qty:
        quantity = qty
    else:
        quantity = (size * 0.97 * float(leverage)) / float(mid_price)
        quantity = round_quantity(quantity, float(qty_step))    

    set_leverage(ticker, leverage)
    try:
        order = place_order(ticker, mid_price, quantity, direction)
    except InvalidRequestError:
        quantity = float(quantity) * 0.97
        quantity = round_quantity(quantity, float(qty_step))
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
