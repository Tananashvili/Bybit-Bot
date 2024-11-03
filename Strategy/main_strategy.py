import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

from func_get_symbols import get_tradeable_symbols
from func_prices_json import store_price_history
from func_cointegration import get_cointegrated_pairs
from func_plot_trends import plot_trends
from helping_functions import send_telegram_message
import pandas as pd
import json
import asyncio

BAD_PAIRS = []

"""STRATEGY CODE"""
if __name__ == "__main__":

    # STEP 1 - Get list of symbols
    print("Getting symbols...")
    sym_response = get_tradeable_symbols()
    # sym_response = sym_response[:200]

    # STEP 2 - Construct and save price history
    print("Constructing and saving price data to JSON...")
    if len(sym_response) > 0:
        store_price_history(sym_response)

    # STEP 3 - Find Cointegrated pairs
    print("Calculating co-integration...")
    with open("1_price_list.json") as json_file:
        price_data = json.load(json_file)
        if len(price_data) > 0:
            coint_pairs = get_cointegrated_pairs(price_data, BAD_PAIRS)

    asyncio.run(send_telegram_message('Done'))

    # # STEP 4 - Plot trends and save for backtesting
    # print("Plotting trends...")
    # symbol_1 = "OPUSDT"
    # symbol_2 = "STEEMUSDT"
    # with open("1_price_list.json") as json_file:
    #     price_data = json.load(json_file)
    #     if len(price_data) > 0:
    #         plot_trends(symbol_1, symbol_2, price_data)
