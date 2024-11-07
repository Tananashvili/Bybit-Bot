import asyncio, os, time
from telegram import Bot
from config_ws_connect import get_orderbook_info
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from func_close_positions import close_all_positions, get_position_info, cancel_all_orders
from func_execution_calls import set_tpsl
from dotenv import load_dotenv
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*utcnow.*")


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def adjust_klines_when_date_changes(series_1, series_2):
    avg1 = sum(series_1) / len(series_1)
    avg2 = sum(series_2) / len(series_2)
    series_1.pop(1)
    series_1[-1] = avg1
    series_2.pop(1)
    series_2[-1] = avg2

    return series_1, series_2


def monitor_zscore():

    global ticker_1, ticker_2, starting_zscore, closing_zscore, stop_loss, starting_date, count

    current_time = datetime.utcnow()
    current_date = current_time.date()

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
        
        if current_date != starting_date:
            series_1, series_2 = adjust_klines_when_date_changes(series_1, series_2)

        series_1.reverse()
        series_2.reverse()

        # Get latest zscore
        _, zscore_list = calculate_metrics(series_1, series_2)
        zscore = zscore_list[-1]

        if abs(zscore) > stop_loss:
            message = f'{ticker_1} - {ticker_2} Position Zscore is Too High: {round(zscore, 2)}'
            asyncio.run(send_telegram_message(message))
            sent = True
        elif count % 15 == 0:
            message = f'{ticker_1} - {ticker_2} Zscore: {round(zscore, 2)}'
            asyncio.run(send_telegram_message(message))

        if abs(zscore) <= abs(closing_zscore):
            close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2)

            while True:
                time.sleep(30)
                side_1, size_1, _ = get_position_info(ticker_1)
                side_2, size_2, _ = get_position_info(ticker_2)

                if float(size_1) > 0 or float(size_2) > 0:
                    cancel_all_orders()
                    close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2)
                else:
                    message = f'{ticker_1} - {ticker_2} Position Closed at Zscore {round(zscore, 2)}'
                    asyncio.run(send_telegram_message(message))
                    closed = True
                    break

    return sent, closed


ticker_1 = "QIUSDT"
ticker_2 = "REQUSDT"
starting_zscore = 2.5
closing_zscore = 1.7
stop_loss = 3.5
count = 15
starting_date = datetime.utcnow().date()

_, _, liq_price_1 = get_position_info(ticker_1)
_, _, liq_price_2 = get_position_info(ticker_2)

set_tpsl(ticker_1, liq_price_1)
set_tpsl(ticker_2, liq_price_2)

while True:
    msg_status, closed = monitor_zscore()
    if closed:
        break
    
    count += 1
    time.sleep(60)