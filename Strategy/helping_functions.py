import math
import os

import pandas as pd
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler
from telegram import Bot

from Strategy.config_strategy_api import (
    entry_zscore,
    max_abs_hedge_ratio,
    max_half_life,
    max_entry_zscore,
    max_symbol_occurrences,
    min_abs_hedge_ratio,
    min_half_life,
    min_zero_crossings,
)


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
    bot_token = os.getenv("bot_token")
    chat_id = os.getenv("chat_id")
    if not bot_token or not chat_id:
        return

    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def calculate_entry_band_score(abs_zscore):
    if max_entry_zscore <= entry_zscore:
        return 1.0

    midpoint = (entry_zscore + max_entry_zscore) / 2
    half_band = (max_entry_zscore - entry_zscore) / 2
    if half_band <= 0:
        return 1.0

    score = 1 - abs(abs_zscore - midpoint) / half_band
    return max(float(score), 0.0)


def filter_data(coint_pairs, output_path="2_cointegrated_pairs.xlsx"):
    if coint_pairs.empty:
        coint_pairs.to_excel(output_path, index=False)
        return

    df = coint_pairs.copy()
    df = df[df["abs"] >= entry_zscore]
    df = df[df["abs"] <= max_entry_zscore]
    df = df[df["zero_crossings"] >= min_zero_crossings]
    df = df[df["half_life"].between(min_half_life, max_half_life)]
    df = df[df["p_value"] <= 0.05]
    df = df[df["hedge_ratio"] > 0]
    df = df[df["hedge_ratio"].abs().between(min_abs_hedge_ratio, max_abs_hedge_ratio)]

    coin_counts = pd.concat([df["sym_1"], df["sym_2"]]).value_counts()
    coins_to_remove = coin_counts[coin_counts > max_symbol_occurrences].index

    df = df[~df["sym_1"].isin(coins_to_remove) & ~df["sym_2"].isin(coins_to_remove)]
    df = df[(df["sym_1"] != "USDCUSDT") & (df["sym_2"] != "USDCUSDT")]
    df = df.sort_values(
        by=["p_value", "half_life", "zero_crossings", "abs"],
        ascending=[True, True, False, False],
    )

    df.to_excel(output_path, index=False)


def pick_best_pair(input_path="2_cointegrated_pairs.xlsx", output_path="2_cointegrated_pairs.xlsx"):
    df = pd.read_excel(input_path)
    if df.empty:
        df.to_excel(output_path, index=False)
        return

    scored_df = df.copy()
    scored_df["entry_band_score"] = scored_df["abs"].apply(calculate_entry_band_score)
    scored_df["inverse_p_value"] = 1 / scored_df["p_value"].clip(lower=1e-6)
    scored_df["inverse_half_life"] = 1 / scored_df["half_life"].clip(lower=1e-6)

    columns = ["entry_band_score", "zero_crossings", "inverse_p_value", "inverse_half_life"]
    weights = {
        "entry_band_score": 0.35,
        "zero_crossings": 0.20,
        "inverse_p_value": 0.30,
        "inverse_half_life": 0.15,
    }

    scaler = MinMaxScaler()
    normalized = pd.DataFrame(scaler.fit_transform(scored_df[columns]), columns=columns)

    scored_df["score"] = (
        normalized["entry_band_score"] * weights["entry_band_score"]
        + normalized["zero_crossings"] * weights["zero_crossings"]
        + normalized["inverse_p_value"] * weights["inverse_p_value"]
        + normalized["inverse_half_life"] * weights["inverse_half_life"]
    )

    scored_df = scored_df.sort_values(by="score", ascending=False).drop(
        columns=["entry_band_score", "inverse_p_value", "inverse_half_life"]
    )
    scored_df.to_excel(output_path, index=False)
