"""
    API Documentation
    https://bybit-exchange.github.io/docs/v5/intro
"""

# API Imports
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

api_key_mainnet = os.getenv('api_key_mainnet')
api_secret_mainnet = os.getenv('api_secret_mainnet')
api_key_testnet = os.getenv('api_key_testnet')
api_secret_testnet = os.getenv('api_secret_testnet')

# CONFIG VARIABLES
mode = "mainnet"
ticker_1 = "ZKJUSDT"
ticker_2 = "ETHBTCUSDT"
leverage = "20"
signal_positive_ticker = ticker_2
signal_negative_ticker = ticker_1
rounding_ticker_1 = 4
rounding_ticker_2 = 6
quantity_rounding_ticker_1 = 0
quantity_rounding_ticker_2 = 1

limit_order_basis = True # will ensure positions (except for Close) will be placed on limit basis

tradeable_capital_usdt = 100 * int(leverage) # total tradeable capital to be split between both pairs
stop_loss_fail_safe = 0.8 # stop loss at market order in case of drastic event
signal_trigger_thresh = 2.5 # z-score threshold which determines trade (must be above zero)

timeframe = 'D' # make sure matches your strategy
kline_limit = 200 # make sure matches your strategy
z_score_window = 21 # make sure matches your strategy

# SELECTED API
api_key = api_key_testnet if mode == "test" else api_key_mainnet
api_secret = api_secret_testnet if mode == "test" else api_secret_mainnet

# SELECTED URL
api_url = "https://api-testnet.bybit.com" if mode == "test" else "https://api.bybit.com"
testnet = True if mode == "test" else False
ws_public_url = "wss://stream-testnet.bybit.com/v5/public/linear" if mode == "test" else "wss://stream.bybit.com/v5/public/linear"

# SESSION Activation
session_public = HTTP(testnet= testnet)
session_private = HTTP(
    testnet=testnet,
    api_key=api_key,
    api_secret=api_secret
)
