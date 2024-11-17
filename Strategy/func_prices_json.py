from Strategy.func_price_klines import get_price_klines
from Strategy.helping_functions import get_orderbook_info, get_trade_details, extract_close_prices
from pybit.exceptions import InvalidRequestError
import json

# Store price histry for all available pairs
def store_price_history(symbols):

    # Get prices and store in DataFrame
    counts = 0
    price_history_dict = {}
    for sym in symbols:
        symbol_name = sym["symbol"]

        try:
            orderbook = get_orderbook_info(symbol_name)
        except InvalidRequestError:
            continue
        mid_price = get_trade_details(orderbook)

        price_history = get_price_klines(symbol_name)
        series = extract_close_prices(price_history)

        if len(series) > 0:
            if mid_price:
                series[0] = mid_price
                series.reverse()

            price_history_dict[symbol_name] = series
            print(f"{counts} items stored")
        else:
            print(f"{counts} items not stored")
        counts += 1

    # Output prices to JSON
    if len(price_history_dict) > 0:
        with open("1_price_list.json", "w") as fp:
            json.dump(price_history_dict, fp, indent=4)
        print("Prices saved successfully.")

    # Return output
    return
