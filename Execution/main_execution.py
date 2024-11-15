import asyncio, os, time, warnings, json
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd
from config_ws_connect import get_orderbook_info
from config_execution_api import get_position_variables
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_stats import calculate_metrics
from func_close_positions import close_all_positions, get_position_info, cancel_order, cancel_all_orders
from func_execution_calls import initialise_order_execution, check_order_status, set_tpsl, get_wallet_balance
from helping_functions import adjust_klines_when_date_changes
from zscore_updates import get_latest_zscore

warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*utcnow.*")


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def monitor_zscore(ticker_1, ticker_2, direction_1, direction_2, starting_date, stop_loss, closing_zscore, count):

    current_time = datetime.utcnow()
    current_date = current_time.date()

    # Get latest asset orderbook prices and add dummy price for latest
    orderbook_1 = get_orderbook_info(ticker_1)
    mid_price_1 = get_trade_details(orderbook_1, direction_1)
    orderbook_2 = get_orderbook_info(ticker_2)
    mid_price_2 = get_trade_details(orderbook_2, direction_2)

    # Get latest price history
    series_1, series_2 = get_latest_klines(ticker_1, ticker_2)
    sent = False
    closed = False
    tpsl_filled = False

    # Check if position is still active
    side_1, size_1, _ = get_position_info(ticker_1)
    side_2, size_2, _ = get_position_info(ticker_2)

    if float(size_1) == 0 or float(size_2) == 0:
        tpsl_filled = True

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

        if abs(zscore) > abs(stop_loss):
            message = f'{ticker_1} - {ticker_2} Position Zscore is Critical! {round(zscore, 2)}'
            asyncio.run(send_telegram_message(message))
            sent = True
        elif count % 15 == 0:
            message = f'{ticker_1} - {ticker_2} Zscore: {round(zscore, 2)}'
            asyncio.run(send_telegram_message(message))

        if abs(zscore) <= abs(closing_zscore) or tpsl_filled:              
            close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2, direction_1)

            while True:
                time.sleep(30)
                
                orderbook_1 = get_orderbook_info(ticker_1)
                mid_price_1 = get_trade_details(orderbook_1, direction_1)
                orderbook_2 = get_orderbook_info(ticker_2)
                mid_price_2 = get_trade_details(orderbook_2, direction_2)
                side_1, size_1, _ = get_position_info(ticker_1)
                side_2, size_2, _ = get_position_info(ticker_2)

                if float(size_1) > 0 or float(size_2) > 0:
                    cancel_all_orders()
                    close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2, direction_1)

                else:
                    if tpsl_filled:
                        message = f'Liquidated {ticker_1} - {ticker_2} Position at Zscore {round(zscore, 2)}'
                    else:
                        message = f'CONGRATS!!! {ticker_1} - {ticker_2} Position Closed at Zscore {round(zscore, 2)}'
                    
                    asyncio.run(send_telegram_message(message))
                    closed = True
                    break

    return sent, closed


def execute():
    # GET POSITION CONFIGURATIONS
    config = get_position_variables()

    ticker_1 = config['ticker_1']
    ticker_2 = config['ticker_2']

    starting_zscore = config['starting_zscore']
    closing_zscore = config['closing_zscore']
    stop_loss = config['stop_loss']
    open_positions = config['open_positions']

    direction_1 = "Short" if starting_zscore > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"

    # PLACE ORDER
    if open_positions:
        order_1 = initialise_order_execution(ticker_1, direction_1)
        order_2 = initialise_order_execution(ticker_2, direction_2)

        if order_1 and order_2:
            while True:

                time.sleep(60)
                order_1_status, left_qty_1 = check_order_status(ticker_1)
                order_2_status, left_qty_2 = check_order_status(ticker_2)

                if order_1_status == 'Filled' and order_2_status == 'Filled':
                    asyncio.run(send_telegram_message('Both Orders Filled!'))
                    _, _, liq_price_1 = get_position_info(ticker_1)
                    _, _, liq_price_2 = get_position_info(ticker_2)

                    set_tpsl(ticker_1, liq_price_1)
                    set_tpsl(ticker_2, liq_price_2)
                    break

                if order_1_status != 'Filled':
                    cancel_order(ticker_1, order_1)
                    order_1 = initialise_order_execution(ticker_1, direction_1, left_qty_1)
                
                if order_2_status != 'Filled':
                    cancel_order(ticker_2, order_2)
                    order_2 = initialise_order_execution(ticker_2, direction_2, left_qty_2)

        else:
            asyncio.run(send_telegram_message("Couldn't Place Order!"))

    count = 11
    starting_date = datetime.utcnow().date()

    while True:
        if count % 10 == 0:
            config = get_position_variables()

            starting_zscore = config['starting_zscore']
            closing_zscore = config['closing_zscore']
            stop_loss = config['stop_loss']

        msg_status, closed = monitor_zscore(ticker_1, ticker_2, direction_1, direction_2, starting_date, stop_loss, closing_zscore, count)
        if closed:
            break
        
        count += 1
        time.sleep(60)


def pick_pair():

    config = get_position_variables()
    df = pd.read_excel('2_cointegrated_pairs.xlsx')
    top_20 = df.head(20)

    if config['open_positions']:
        while True:
            for index, row in top_20.iterrows():
                ticker_1 = row['sym_1']
                ticker_2 = row['sym_2']
                zscore = row['z_score']
                direction_1 = "Short" if zscore > 0 else "Long"
                direction_2 = "Long" if direction_1 == "Short" else "Short"
                
                new_zscore = get_latest_zscore(ticker_1, ticker_2, direction_1, direction_2, True)
                
                if abs(new_zscore) > abs(zscore) * 1.3:
                    capital = get_wallet_balance()
                    config_data = {
                        "ticker_1": ticker_1,
                        "ticker_2": ticker_2,
                        "starting_zscore": new_zscore,
                        "closing_zscore": new_zscore * 0.75,
                        "stop_loss": new_zscore * 1.25,
                        "capital": capital * 0.97,
                        "leverage": config['leverage'],
                        "open_positions": config['open_positions']
                    }
                    asyncio.run(send_telegram_message(f"Pair Found: {ticker_1} - {ticker_2}, Zscore is {new_zscore} Opening Positions..."))

                    with open('config.json', 'w') as json_file:
                        json.dump(config_data, json_file, indent=4)
                    
                    execute()
                    return
    else:
        execute()
        return

if __name__ == "__main__":
    pick_pair()