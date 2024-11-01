import asyncio, os
from telegram import Bot
from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from helping_functions import plot_trends
from dotenv import load_dotenv


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


# Get latest z-score
def get_latest_zscore(ticker_1, ticker_2, starting_zscore, target_zscore, stop_loss):

    direction_1 = "Short" if starting_zscore > 0 else "Long"
    direction_2 = "Short" if direction_1 == "Long" else "Long"

    # Get latest asset orderbook prices and add dummy price for latest
    orderbook_1 = get_orderbook_info(ticker_1)
    mid_price_1, _, _, = get_trade_details(orderbook_1, direction_1, 0)
    orderbook_2 = get_orderbook_info(ticker_2)
    mid_price_2, _, _, = get_trade_details(orderbook_2, direction_2, 0)

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

        if abs(zscore) < target_zscore:
            message = f'{ticker_1} - {ticker_2} Position Zscore is Low ({round(zscore, 2)}), Close Positions'
            asyncio.run(send_telegram_message(message))
        elif abs(zscore) > stop_loss:
            message = f'{ticker_1} - {ticker_2} Position Zscore is Too High ({round(zscore, 2)})'
            asyncio.run(send_telegram_message(message))

        # plot = input('Plot Trends? ')
        # if plot == 'yes' or plot == 'y':
        #     plot_trends(symbols[0], symbols[1], series_1, series_2)


symbols = ["EIGENUSDT", "BNXUSDT"]
starting_zscore = 2.63
target_zscore = 1.5
stop_loss = 3.5
get_latest_zscore(symbols[0], symbols[1], starting_zscore, target_zscore, stop_loss)
