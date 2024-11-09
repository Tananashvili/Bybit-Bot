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
def get_trade_details(orderbook, direction):

    mid_price = 0
    bid_items_list = []
    ask_items_list = []

    # Get prices, stop loss and quantity
    if orderbook:

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
            if direction == "Short":
                mid_price = nearest_bid # placing at Bid has high probability of not being cancelled, but may not fill
            else:
                mid_price = nearest_ask  # placing at Ask has high probability of not being cancelled, but may not fill

    # Output results
    return mid_price
