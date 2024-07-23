from config_execution_api import session_private

# Check for open positions
def open_position_confirmation(ticker):
    try:
        position = session_private.get_positions(
            category="linear",
            symbol=ticker
            )

        if position["retMsg"] == "OK":
            for item in position["result"]["list"]:
                if float(item["size"]) > 0 and item['liqPrice']:
                    return True
    except:
        return True
    return False


# Check for active positions
def active_position_confirmation(ticker):
    try:
        active_order = session_private.get_open_orders(
            category="linear",
            symbol=ticker,
        )

        if active_order["retMsg"] == "OK":
            if len(active_order["result"]["list"]) > 0:
                return True
    except:
        return True
    return False


# Get open position price and quantity
def get_open_positions(ticker):

    # Get position
    active_order = session_private.get_positions(
            category="linear",
            symbol=ticker
            )

    # Construct a response
    if "retMsg" in active_order.keys():
        if active_order["retMsg"] == "OK":
            if len(active_order["result"]["list"]) > 0:
                for trade in active_order["result"]["list"]:
                    if ticker in trade["symbol"]:
                        order_price = trade["avgPrice"]
                        order_quantity = trade["size"]
                        return order_price, order_quantity
            return (0, 0)
    return (0, 0)


# Get active position price and quantity
def get_active_positions(ticker):

    # Get position
    position = session_private.get_open_orders(
        category="linear",
        symbol=ticker,
    )

    # Construct a response
    if "retMsg" in position.keys():
        if position["retMsg"] == "OK":
            for trade in position["result"]["list"]:
                if "symbol" in trade.keys():
                    order_price = trade["price"]
                    order_quantity = trade["qty"]
                    return order_price, order_quantity
                return (0, 0)
    return (0, 0)


# Query existing order
def query_existing_order(order_id):

    # Query order
    order = session_private.get_open_orders(
    category="linear",
    orderId=order_id
    )

    # Construct response
    if "retMsg" in order.keys():
        if order["retMsg"] == "OK":
            order_price = order["result"]["list"][0]["price"]
            order_quantity = order["result"]["list"][0]["qty"]
            order_status = order["result"]["list"][0]["orderStatus"]
            return order_price, order_quantity, order_status
    return (0, 0, 0)
