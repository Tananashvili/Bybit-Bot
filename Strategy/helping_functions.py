from config_strategy_api import session_public
import math
from dotenv import load_dotenv
import os
from telegram import Bot
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def get_orderbook_info(ticker):
    orderbook = session_public.get_orderbook(
        category="linear",
        symbol=ticker,
        limit=25
    )

    return orderbook


def get_trade_details(orderbook):

    # Set calculation and output variables
    mid_price = 0
    bid_items_list = []

    # Get prices, stop loss and quantity
    if orderbook:

        bid_items_list.append(orderbook['result']["b"])
        # Calculate price, size, stop loss and average liquidity
        if len(bid_items_list) > 0:

            # Sort lists
            bid_items_list.sort()
            bid_items_list.reverse()
            try:
                nearest_bid = float(bid_items_list[0][0][0])
                mid_price = nearest_bid # placing at Bid has high probability of not being cancelled, but may not fill
            except IndexError:
                mid_price = None

    # Output results
    return mid_price


# Puts all close prices in a list
def extract_close_prices(prices):
    close_prices = []
    for price_values in prices:
        close_price = float(price_values[-1])
        if math.isnan(close_price):
            return []
        close_prices.append(close_price)
    return close_prices


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv('bot_token')
    chat_id = os.getenv('chat_id')
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def filter_data(coint_pairs):

    df = coint_pairs

    df = df[df['abs'] >= 2]
    df = df[df['zero_crossings'] >= 25]

    coin_counts = pd.concat([df['sym_1'], df['sym_2']]).value_counts()
    coins_to_remove = coin_counts[coin_counts > 5].index
    
    df = df[~df['sym_1'].isin(coins_to_remove) & ~df['sym_2'].isin(coins_to_remove)]
    df = df[(df['sym_1'] != 'USDCUSDT') & (df['sym_2'] != 'USDCUSDT')]
    df = df.sort_values(by=['zero_crossings', 'abs'], ascending=[False, False])

    df.to_excel('2_cointegrated_pairs.xlsx', index=False)


def pick_best_pair():  

    df = pd.read_excel('2_cointegrated_pairs.xlsx')

    columns = ['abs', 'zero_crossings', 'hedge_ratio']
    weights = {'abs': 0.4, 'zero_crossings': 0.4, 'hedge_ratio': 0.2}

    scaler = MinMaxScaler()
    df_normalized = pd.DataFrame(scaler.fit_transform(df[columns]), columns=columns)

    df['score'] = (df_normalized['abs'] * weights['abs'] +
                df_normalized['zero_crossings'] * weights['zero_crossings'] +
                df_normalized['hedge_ratio'] * weights['hedge_ratio'])

    df_sorted = df.sort_values(by='score', ascending=False)
    df_sorted.to_excel('2_cointegrated_pairs.xlsx', index=False)

    best_row = df_sorted[['sym_1', 'sym_2']].iloc[0]
    return f'Best Pair: {best_row['sym_1']} - {best_row['sym_2']}'
