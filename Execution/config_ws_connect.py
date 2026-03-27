from Execution.config_execution_api import session_public


def get_orderbook_info(ticker):
    orderbook = session_public.get_orderbook(
        category="linear",
        symbol=ticker,
        limit=25
    )

    return orderbook
