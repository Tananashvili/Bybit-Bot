from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

api_key_mainnet = os.getenv('api_key_mainnet')
api_secret_mainnet = os.getenv('api_secret_mainnet')
api_key_testnet = os.getenv('api_key_testnet')
api_secret_testnet = os.getenv('api_secret_testnet')

# POSITION VARIABLES
ticker_1 = "XVSUSDT"
ticker_2 = "POWRUSDT"
starting_zscore = 2.2
closing_zscore = 0
stop_loss = 3
capital = 395

# CONFIG VARIABLES
mode = "main"
leverage = "10"
limit_order_basis = True 

direction_1 = "Short" if starting_zscore > 0 else "Long"
direction_2 = "Long" if direction_1 == "Short" else "Short"

timeframe = 'D' 
kline_limit = 200 
z_score_window = 21 

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
