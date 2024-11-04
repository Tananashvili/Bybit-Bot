from config_execution_api import (
    signal_positive_ticker,
    signal_negative_ticker,
    session_private,
)
import pybit.exceptions


# Get position information
def get_position_info(ticker):

    # Declare output variables
    side = 0
    size = ""
    liq = ""

    # Extract position info
    position = session_private.get_positions(category="linear", symbol=ticker)
    if "retMsg" in position.keys():
        if position["retMsg"] == "OK":
            size = position["result"]["list"][0]["size"]
            side = position["result"]["list"][0]["side"]
            liq = ["result"]["list"][0]["liqPrice"]

    # Return output
    return side, size, liq


#  Place market close order
def place_market_close_order(ticker, side, size):

    # Close position
    try:
        session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Market",
            qty=size,
            isLeverage=0,
        )
        print(f"{ticker} Order Closed Successfully!")
    except pybit.exceptions.InvalidRequestError as e:
        print(e)
        print(f"Couldn't Close Order: {ticker}")
    # Return
    return


def place_limit_close_order(ticker, side, size, mid_price):

    # Close position
    try:
        session_private.place_order(
            category="linear",
            symbol=ticker,
            side=side,
            orderType="Limit",
            qty=size,
            price=mid_price,
        )
        print(f"{ticker} Close Order Created!")
    except pybit.exceptions.InvalidRequestError as e:
        print(e)
        print(f"Couldn't Close Order: {ticker}")
    # Return
    return


# Close all positions for both tickers
def close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2):

    # Get position information
    side_1, size_1, _ = get_position_info(ticker_1)
    side_2, size_2, _ = get_position_info(ticker_2)

    if float(size_1) > 0:
        # place_market_close_order(ticker_1, side_2, size_1)  # use side 2
        place_limit_close_order(ticker_1, side_2, size_1, mid_price_1)

    if float(size_2) > 0:
        # place_market_close_order(ticker_2, side_1, size_2)  # use side 1
        place_limit_close_order(ticker_2, side_1, size_2, mid_price_2)

    # Output results
    kill_switch = 0
    return kill_switch


def cancel_all_orders():
    session_private.cancel_all_orders(category="linear", settleCoin="USDT")