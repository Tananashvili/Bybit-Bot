import asyncio, os, time
from telegram import Bot
from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from func_close_positions import close_all_positions
from dotenv import load_dotenv


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


# Get latest z-score
def get_latest_zscore(ticker_1, ticker_2, starting_zscore, target_zscore, closing_zscore, stop_loss):

    direction_1 = "Short" if starting_zscore > 0 else "Long"
    direction_2 = "Short" if direction_1 == "Long" else "Long"

    # Get latest asset orderbook prices and add dummy price for latest
    orderbook_1 = get_orderbook_info(ticker_1)
    mid_price_1, _, _, = get_trade_details(ticker_1, orderbook_1, direction_1, 0)
    orderbook_2 = get_orderbook_info(ticker_2)
    mid_price_2, _, _, = get_trade_details(ticker_2, orderbook_2, direction_2, 0)

    # Get latest price history
    series_1, series_2 = get_latest_klines(ticker_1, ticker_2)
    sent = False
    closed = False

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

        if abs(zscore) < target_zscore:
            message = f'{ticker_1} - {ticker_2} Position Zscore is Low ({round(zscore, 2)}), Close Positions'
            asyncio.run(send_telegram_message(message))
            sent = True
        elif abs(zscore) > stop_loss:
            message = f'{ticker_1} - {ticker_2} Position Zscore is Too High ({round(zscore, 2)})'
            asyncio.run(send_telegram_message(message))
            sent = True

        if abs(zscore) <= abs(closing_zscore):
            close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2)
            closed = True
    
    return sent, closed


symbols = ["OPUSDT", "STEEMUSDT"]
starting_zscore = 2.54
target_zscore = 1.3
closing_zscore = 0.8
stop_loss = 3.2

while True:
    msg_status, position_status = get_latest_zscore(symbols[0], symbols[1], starting_zscore, target_zscore, closing_zscore, stop_loss)
    if position_status:
        break

    time.sleep(60)