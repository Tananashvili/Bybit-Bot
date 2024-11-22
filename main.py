import warnings, json, asyncio
from datetime import datetime, timedelta
from Strategy.func_get_symbols import get_tradeable_symbols
from Strategy.func_prices_json import store_price_history
from Strategy.func_cointegration import get_cointegrated_pairs
from Strategy.helping_functions import send_telegram_message, filter_data, pick_best_pair
from Execution.main_execution import pick_pair

warnings.simplefilter(action="ignore", category=FutureWarning)

BAD_PAIRS = []
starting_time = datetime.utcnow()
count = 0

while True:

    current_time = datetime.utcnow()
    time_difference = current_time - starting_time
    if time_difference >= timedelta(hours=2) or count == 0:

        asyncio.run(send_telegram_message("Getting Pairs..."))
        sym_response = get_tradeable_symbols()

        if len(sym_response) > 0:
            store_price_history(sym_response)

        with open("1_price_list.json") as json_file:
            price_data = json.load(json_file)
            if len(price_data) > 0:
                coint_pairs = get_cointegrated_pairs(price_data, BAD_PAIRS)

        filter_data(coint_pairs)
        pick_best_pair()
        asyncio.run(send_telegram_message("Pairs filtered. Searching best one..."))
        count += 1
    
    pick_pair()