import asyncio
import json
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

from Execution.config_execution_api import load_runtime_config
from Execution.main_execution import run_portfolio_cycle
from Strategy.func_cointegration import get_cointegrated_pairs
from Strategy.func_get_symbols import get_tradeable_symbols
from Strategy.func_prices_json import store_price_history
from Strategy.helping_functions import filter_data, pick_best_pair, send_telegram_message

warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

bad_pairs = []
last_refresh_time = datetime.min

while True:
    runtime_config = load_runtime_config()
    refresh_interval = timedelta(hours=float(runtime_config["pair_refresh_hours"]))

    if datetime.utcnow() - last_refresh_time >= refresh_interval:
        asyncio.run(send_telegram_message("Refreshing candidate pairs from mainnet data..."))
        symbols = get_tradeable_symbols()
        if symbols:
            store_price_history(symbols)

        price_data = {}
        price_file = Path("1_price_list.json")
        if price_file.exists():
            with price_file.open("r", encoding="utf-8") as json_file:
                price_data = json.load(json_file)

        coint_pairs = get_cointegrated_pairs(price_data, bad_pairs) if price_data else None
        if coint_pairs is not None:
            filter_data(coint_pairs)
            pick_best_pair()

        bad_pairs = []
        last_refresh_time = datetime.utcnow()

    bad_pairs = run_portfolio_cycle(bad_pairs)
    bad_pairs = list(dict.fromkeys(bad_pairs))
    time.sleep(int(runtime_config["loop_sleep_seconds"]))
