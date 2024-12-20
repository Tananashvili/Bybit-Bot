from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from helping_functions import plot_trends


# Get latest z-score
def get_latest_zscore(ticker_1, ticker_2, starting_zscore, target_zscore, stop_loss):

    direction_1 = "Short" if starting_zscore > 0 else "Long"
    direction_2 = "Short" if direction_1 == "Long" else "Long"

    # Get latest asset orderbook prices and add dummy price for latest
    orderbook_1 = get_orderbook_info(ticker_1)
    mid_price_1, _, _, = get_trade_details(ticker_1, orderbook_1, direction_1, 0)
    orderbook_2 = get_orderbook_info(ticker_2)
    mid_price_2, _, _, = get_trade_details(ticker_2, orderbook_2, direction_2, 0)

    # Get latest price history
    series_1, series_2 = get_latest_klines(ticker_1, ticker_2)

    # Get z_score and confirm if hot
    if len(series_1) > 0 and len(series_2) > 0:

        # Replace last kline price with latest orderbook mid price
        series_1[0] = mid_price_1
        series_2[0] = mid_price_2
        series_1.reverse()
        series_2.reverse()

        # Get latest zscore
        _, zscore_list = calculate_metrics(series_1, series_2)
        zscore = zscore_list[-1]

        print(zscore)
        plot_trends(symbols[0], symbols[1], series_1, series_2)


symbols = ["MDTUSDT", "MOVRUSDT"]
starting_zscore = 2.15
target_zscore = 1.35
stop_loss = 3.25
get_latest_zscore(symbols[0], symbols[1], starting_zscore, target_zscore, stop_loss)