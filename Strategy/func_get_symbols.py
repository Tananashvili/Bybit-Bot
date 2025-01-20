from config_strategy_api import session

# Get symbols that are tradeable
def get_tradeable_symbols():

    symbols = session.get_instruments_info(
        category="linear",
    )
    # Get available symbols
    sym_list = []
    if "retMsg" in symbols.keys():
        if symbols["retMsg"] == "OK":
            symbols = symbols["result"]["list"]
            for symbol in symbols:
                if symbol["quoteCoin"] == "USDT" and float(symbol["lowerFundingRate"]) < 0 and symbol["status"] == "Trading":
                    sym_list.append(symbol)

    return sym_list
