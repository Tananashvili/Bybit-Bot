import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

from Strategy.func_get_symbols import get_tradeable_symbols
from Strategy.func_prices_json import store_price_history
from Strategy.func_cointegration import get_cointegrated_pairs
from Strategy.helping_functions import filter_data, pick_best_pair
import json

BAD_PAIRS = []

"""STRATEGY CODE"""
if __name__ == "__main__":

    # STEP 1 - Get list of symbols
    print("Getting symbols...")
    sym_response = get_tradeable_symbols()

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

    # STEP 4 - Filter Database
    filter_data(coint_pairs)
    pick_best_pair()
