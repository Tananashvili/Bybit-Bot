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

    # Extract position info
    position = session_private.get_positions(category="linear", symbol=ticker)
    if "retMsg" in position.keys():
        if position["retMsg"] == "OK":
            size = position["result"]["list"][0]["size"]
            side = position["result"]["list"][0]["side"]

    # Return output
    return side, size


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


# Close all positions for both tickers
def close_all_positions(kill_switch):

    # Get position information
    side_1, size_1 = get_position_info(signal_positive_ticker)
    side_2, size_2 = get_position_info(signal_negative_ticker)

    if float(size_1) > 0:
        place_market_close_order(signal_positive_ticker, side_2, size_1)  # use side 2

    if float(size_2) > 0:
        place_market_close_order(signal_negative_ticker, side_1, size_2)  # use side 1

    # Cancel all active orders
    session_private.cancel_all_orders(category="linear", settleCoin="USDT")

    # Output results
    kill_switch = 0
    return kill_switch
