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

# CONFIG
mode = "mainnet"
timeframe = 60
kline_limit = 200
z_score_window = 21

# SELECTED API
api_key = api_key_testnet if mode == "test" else api_key_mainnet
api_secret = api_secret_testnet if mode == "test" else api_secret_mainnet

# SELECTED URL
api_url = "https://api-testnet.bybit.com" if mode == "test" else "https://api.bybit.com"
testnet = True if mode == "test" else False

# SESSION Activation
session_public = HTTP(testnet= testnet)
session = HTTP(
    testnet=testnet,
    api_key=api_key,
    api_secret=api_secret
)
