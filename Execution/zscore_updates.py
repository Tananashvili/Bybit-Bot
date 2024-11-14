from config_ws_connect import get_orderbook_info
from config_execution_api import get_position_variables
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from helping_functions import plot_trends


# Get latest z-score
def get_latest_zscore(ticker_1=False, ticker_2=False, direction_1=False, direction_2=False, called=False):

    # Get position variables
    if not ticker_1:
        config = get_position_variables()
        ticker_1 = config['ticker_1']
        ticker_2 = config['ticker_2']
        direction_1 = config['direction_1']
        direction_2 = config['direction_2']

    # Get latest asset orderbook prices and add dummy price for latest
    orderbook_1 = get_orderbook_info(ticker_1)
    mid_price_1 = get_trade_details(orderbook_1, direction_1)
    orderbook_2 = get_orderbook_info(ticker_2)
    mid_price_2 = get_trade_details(orderbook_2, direction_2)

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

    if called:
        return zscore
    
    else:
        print(zscore)
        # plot_trends(ticker_1, ticker_2, series_1, series_2)


if "__main__" == __name__:
    get_latest_zscore()