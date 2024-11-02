from config_strategy_api import session_public
import math
from dotenv import load_dotenv
import os
from telegram import Bot


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