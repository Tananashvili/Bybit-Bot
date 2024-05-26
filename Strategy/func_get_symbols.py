from config_strategy_api import session
import requests

# Get symbols that are tradeable
def get_tradeable_symbols():
    url = "https://api-testnet.bybit.com/v5/market/instruments-info?category=linear"
    response = requests.get(url)
    symbols = response.json()

    # Get available symbols
    sym_list = []
    if "retMsg" in symbols.keys():
        if symbols["retMsg"] == "OK":
            symbols = symbols["result"]["list"]
            for symbol in symbols:
                if symbol["quoteCoin"] == "USDT" and float(symbol["lowerFundingRate"]) < 0 and symbol["status"] == "Trading":
                    sym_list.append(symbol)

    return sym_list
