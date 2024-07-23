from config_execution_api import stop_loss_fail_safe, ticker_1, rounding_ticker_1, rounding_ticker_2, quantity_rounding_ticker_1, quantity_rounding_ticker_2
import math


# Puts all close prices in a list
def extract_close_prices(prices):
    close_prices = []
    for price_values in prices:
        if math.isnan(float(price_values[-1])):
            return []
        close_prices.append(float(price_values[-1]))
    return close_prices


# Get trade details and latest prices
def get_trade_details(orderbook, direction, capital):

    # Set calculation and output variables
    price_rounding = 20
    quantity_rounding = 20
    mid_price = 0
    quantity = 0
    stop_loss = 0
    bid_items_list = []
    ask_items_list = []

    # Get prices, stop loss and quantity
    if orderbook:

        # Set price rounding
        price_rounding = rounding_ticker_1 if orderbook['result']["s"] == ticker_1 else rounding_ticker_2
        quantity_rounding = quantity_rounding_ticker_1 if orderbook['result']["s"] == ticker_1 else quantity_rounding_ticker_2

        bid_items_list.append(orderbook['result']["b"])
        ask_items_list.append(orderbook['result']["a"])

        # Calculate price, size, stop loss and average liquidity
        if len(ask_items_list) > 0 and len(bid_items_list) > 0:

            # Sort lists
            ask_items_list.sort()
            bid_items_list.sort()
            bid_items_list.reverse()

            # Get nearest ask, nearest bid and orderbook spread
            nearest_ask = float(ask_items_list[0][0][0])
            nearest_bid = float(bid_items_list[0][0][0])

            # Calculate hard stop loss
            if direction == "Long":
                mid_price = nearest_bid # placing at Bid has high probability of not being cancelled, but may not fill
                stop_loss = round(mid_price * (1 - stop_loss_fail_safe), price_rounding)
            else:
                mid_price = nearest_ask  # placing at Ask has high probability of not being cancelled, but may not fill
                stop_loss = round(mid_price * (1 + stop_loss_fail_safe), price_rounding)

            # Calculate quantity
            quantity = round(capital / mid_price, quantity_rounding)

    # Output results
    return (mid_price, stop_loss, quantity)
