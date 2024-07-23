"""
    API Documentation
    https://bybit-exchange.github.io/docs/v5/intro
"""

# API Imports
from pybit.unified_trading import HTTP

# CONFIG VARIABLES
mode = "test"
ticker_1 = "ADAUSDT"
ticker_2 = "AXSUSDT"
leverage = "5"
signal_positive_ticker = ticker_2
signal_negative_ticker = ticker_1
rounding_ticker_1 = 4
rounding_ticker_2 = 3
quantity_rounding_ticker_1 = 0
quantity_rounding_ticker_2 = 1

limit_order_basis = True # will ensure positions (except for Close) will be placed on limit basis

tradeable_capital_usdt = 200 * int(leverage) # total tradeable capital to be split between both pairs
stop_loss_fail_safe = 1 # stop loss at market order in case of drastic event
signal_trigger_thresh = 1.5 # z-score threshold which determines trade (must be above zero)

timeframe = 60 # make sure matches your strategy
kline_limit = 200 # make sure matches your strategy
z_score_window = 21 # make sure matches your strategy

# LIVE API
api_key_mainnet = ""
api_secret_mainnet = ""

# TEST API
api_key_testnet = "6QXmiBa5TcgIzjEcub"
api_secret_testnet = "ELBHgBz9tNnifqRmtfpLdGzExiOQUgxLCtuw"

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
