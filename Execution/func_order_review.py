from func_position_calls import query_existing_order, get_open_positions, get_active_positions
from func_calcultions import get_trade_details
from config_ws_connect import get_orderbook_info


# Check order items
def check_order(ticker, order_id, remaining_capital, direction="Long"):

    # Get current orderbook
    orderbook = get_orderbook_info(ticker)

    # Get latest price
    # mid_price, _, _ = get_trade_details(orderbook)

    # Get trade details
    order_price, order_quantity, order_status = query_existing_order(order_id)

    # Get open positions
    position_price, position_quantity = get_open_positions(ticker)

    # Get active positions
    # active_order_price, active_order_quantity = get_active_positions(ticker)

    # Determine action - trade complete - stop placing orders
    if float(position_quantity) >= remaining_capital and float(position_quantity) > 0:
        print(f"position_quantity {position_quantity}", f"remaining_capital {remaining_capital}")
        return "Trade Complete"

    # Determine action - position filled - buy more
    if order_status == "Filled":
        return "Position Filled"

    # Determine action - order active - do nothing
    active_items = ["Untriggered", "New"]
    if order_status in active_items:
        return "Order Active"

    # Determine action - partial filled order - do nothing
    if order_status == "PartiallyFilled":
        return "Partial Fill"

    # Determine action - order failed - try place order again
    cancel_items = ["Cancelled", "Rejected", "Deactivated"]
    if order_status in cancel_items:
        return "Try Again"
