from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os, json

load_dotenv()

api_key_mainnet = os.getenv('api_key_mainnet')
api_secret_mainnet = os.getenv('api_secret_mainnet')
api_key_testnet = os.getenv('api_key_testnet')
api_secret_testnet = os.getenv('api_secret_testnet')

# POSITION VARIABLES
def get_position_variables():

    with open('config.json', 'r') as f:
        config = json.load(f)

    ticker_1 = config['ticker_1']
    ticker_2 = config['ticker_2']

    starting_zscore = config['starting_zscore']
    desired_profit = config['desired_profit']
    stop_loss = config['stop_loss']

    leverage = config['leverage']
    open_positions = config['open_positions']

    direction_1 = "Short" if starting_zscore > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"

    return {'ticker_1': ticker_1, 'ticker_2': ticker_2, 'starting_zscore': starting_zscore, 'desired_profit': desired_profit,
            'stop_loss': stop_loss, 'leverage': leverage, 'open_positions': open_positions,
            'direction_1': direction_1, 'direction_2': direction_2}

# CONFIG VARIABLES
mode = "main"
limit_order_basis = True 

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
