import asyncio, os, time, json
from telegram import Bot
from dotenv import load_dotenv
import pandas as pd
from config_ws_connect import get_orderbook_info
from config_execution_api import get_position_variables
from func_calcultions import get_trade_details
from func_price_calls import get_latest_klines
from func_close_positions import close_all_positions, get_position_info, cancel_order, cancel_all_orders
from func_execution_calls import initialise_order_execution, check_order_status, set_tpsl, get_wallet_balance
from zscore_updates import get_latest_zscore


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def monitor_zscore(ticker_1, ticker_2, direction_1, direction_2, stop_loss, desired_profit, count):

    # Get latest price history
    series_1, series_2 = get_latest_klines(ticker_1, ticker_2)
    closed = False
    tpsl_filled = False

    # Check if position is still active
    side_1, size_1, change_percent_1 = get_position_info(ticker_1, True)
    side_2, size_2, change_percent_2 = get_position_info(ticker_2, True)
    change_percent = round(float(change_percent_1) + float(change_percent_2), 1)

    if float(size_1) == 0 or float(size_2) == 0:
        tpsl_filled = True

    # Get z_score and confirm if hot
    if len(series_1) > 0 and len(series_2) > 0:

        if change_percent <= -stop_loss and count % 3 == 0:
            message = f'{ticker_1} - {ticker_2} Position PnL is Below SL: {change_percent}%'
            asyncio.run(send_telegram_message(message))

        elif count % 20 == 0:
            message = f'{ticker_1} - {ticker_2} PnL: {change_percent}%'
            asyncio.run(send_telegram_message(message))

        if change_percent >= desired_profit or tpsl_filled:

            orderbook_1 = get_orderbook_info(ticker_1)
            mid_price_1 = get_trade_details(orderbook_1, direction_1)
            orderbook_2 = get_orderbook_info(ticker_2)
            mid_price_2 = get_trade_details(orderbook_2, direction_2)

            close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2, direction_1)

            while True:
                time.sleep(30)
                side_1, size_1, _ = get_position_info(ticker_1)
                side_2, size_2, _ = get_position_info(ticker_2)

                if float(size_1) > 0 or float(size_2) > 0:

                    orderbook_1 = get_orderbook_info(ticker_1)
                    mid_price_1 = get_trade_details(orderbook_1, direction_1)
                    orderbook_2 = get_orderbook_info(ticker_2)
                    mid_price_2 = get_trade_details(orderbook_2, direction_2)

                    cancel_all_orders()
                    close_all_positions(ticker_1, ticker_2, mid_price_1, mid_price_2, direction_1)

                else:
                    if tpsl_filled:
                        message = f'Liquidated {ticker_1} - {ticker_2} Position. Loss is {change_percent}%'
                    else:
                        message = f'CONGRATS!!! {ticker_1} - {ticker_2} Position Closed. PnL is {change_percent}%'
                    
                    asyncio.run(send_telegram_message(message))
                    closed = True
                    break

    return closed


def execute():
    # GET POSITION CONFIGURATIONS
    config = get_position_variables()

    ticker_1 = config['ticker_1']
    ticker_2 = config['ticker_2']

    desired_profit = config['desired_profit']
    stop_loss = config['stop_loss']
    open_positions = config['open_positions']

    direction_1 = config['direction_1']
    direction_2 = config['direction_2']

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

    count = 15
    while True:
        if count % 10 == 0:
            config = get_position_variables()

            desired_profit = config['desired_profit']
            stop_loss = config['stop_loss']

        closed = monitor_zscore(ticker_1, ticker_2, direction_1, direction_2, stop_loss, desired_profit, count)
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
                
                if abs(new_zscore) > abs(zscore) * 1.4:
                    capital = get_wallet_balance()
                    config_data = {
                        "ticker_1": ticker_1,
                        "ticker_2": ticker_2,
                        "starting_zscore": new_zscore,
                        "desired_profit": config['desired_profit'],
                        "stop_loss": config['stop_loss'],
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