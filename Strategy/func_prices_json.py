import json

from Strategy.func_price_klines import get_price_klines
from Strategy.helping_functions import extract_close_prices


def store_price_history(symbols, output_path="1_price_list.json"):
    price_history_dict = {}

    for sym in symbols:
        symbol_name = sym["symbol"]
        price_history = get_price_klines(symbol_name)
        series = extract_close_prices(price_history)

        if series:
            series.reverse()
            price_history_dict[symbol_name] = series

    if price_history_dict:
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(price_history_dict, file, indent=4)
        print("Prices saved successfully.")
