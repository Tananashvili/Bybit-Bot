"""
    API Documentation
    https://bybit-exchange.github.io/docs/v5/intro
"""

from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

api_key_mainnet = os.getenv("api_key_mainnet")
api_secret_mainnet = os.getenv("api_secret_mainnet")
api_key_testnet = os.getenv("api_key_testnet")
api_secret_testnet = os.getenv("api_secret_testnet")

# Runtime mode
mode = "mainnet"

# Market-data horizon. The strategy and paper execution must use the same horizon.
timeframe = 60
kline_limit = 500
z_score_window = 72
train_window = 250

# Signal and filtering thresholds
entry_zscore = 2.2
exit_zscore = 0.5
stop_zscore = 4.0
min_zero_crossings = 12
min_half_life = 2
max_half_life = 72
min_turnover_24h = 5_000_000
max_spread_bps = 15
max_symbol_occurrences = 4
top_pairs_to_scan = 25

# Selected API credentials
api_key = api_key_testnet if mode == "testnet" else api_key_mainnet
api_secret = api_secret_testnet if mode == "testnet" else api_secret_mainnet
testnet = mode == "testnet"

session_public = HTTP(testnet=testnet)
session = (
    HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret,
    )
    if api_key and api_secret
    else HTTP(testnet=testnet)
)
