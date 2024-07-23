"""
    API Documentation
    https://bybit-exchange.github.io/docs/v5/intro
"""

# API Imports
from pybit.unified_trading import HTTP



# CONFIG
mode = "test"
timeframe = 60
kline_limit = 200
z_score_window = 21

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

# SESSION Activation
session = HTTP(
    testnet=testnet,
    api_key=api_key,
    api_secret=api_secret
)

# # Web Socket Connection
# subs = [
#     "kline.1.BTCUSDT"
# ]
# ws = WebSocket(
#     "wss://stream-testnet.bybit.com/v5/public/linear",
#     subscriptions=subs
# )

# while True:
#     data = ws.fetch(subs[0])
#     if data:
#         print(data)
