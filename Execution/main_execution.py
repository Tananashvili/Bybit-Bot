import asyncio
import csv
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telegram import Bot

from Execution.config_execution_api import PAPER_TRADES_PATH, load_runtime_config, timeframe
from Execution.func_execution_calls import get_instrument_meta
from Execution.func_price_calls import get_ticker_snapshot
from Execution.helping_functions import round_quantity
from Execution.zscore_updates import get_latest_pair_metrics
from Strategy.config_strategy_api import max_half_life, min_half_life, top_pairs_to_scan


async def send_telegram_message(message):
    load_dotenv()
    bot_token = os.getenv("bot_token")
    chat_id = os.getenv("chat_id")
    if not bot_token or not chat_id:
        return

    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def get_executable_price(ticker, direction, action, slippage_bps):
    snapshot = get_ticker_snapshot(ticker)
    try:
        bid_price = float(snapshot["bid1Price"])
        ask_price = float(snapshot["ask1Price"])
    except (KeyError, TypeError, ValueError):
        return None

    if action == "open":
        raw_price = ask_price if direction == "Long" else bid_price
    else:
        raw_price = bid_price if direction == "Long" else ask_price

    slippage_multiplier = 1 + (slippage_bps / 10000)
    if (direction == "Long" and action == "open") or (direction == "Short" and action == "close"):
        return raw_price * slippage_multiplier
    return raw_price / slippage_multiplier


def calculate_leg_pnl(direction, quantity, entry_price, exit_price):
    if direction == "Long":
        return quantity * (exit_price - entry_price)
    return quantity * (entry_price - exit_price)


def append_trade_log(record):
    file_exists = PAPER_TRADES_PATH.exists()
    fieldnames = [
        "opened_at",
        "closed_at",
        "ticker_1",
        "ticker_2",
        "direction_1",
        "direction_2",
        "entry_zscore",
        "exit_zscore",
        "exit_reason",
        "hedge_ratio",
        "intercept",
        "quantity_1",
        "quantity_2",
        "entry_price_1",
        "entry_price_2",
        "exit_price_1",
        "exit_price_2",
        "gross_pnl",
        "fees_paid",
        "net_pnl",
        "return_pct",
    ]

    with PAPER_TRADES_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def build_position_from_candidate(candidate_row, runtime_config):
    live_metrics = get_latest_pair_metrics(candidate_row["sym_1"], candidate_row["sym_2"])
    if live_metrics is None:
        return None

    live_zscore = live_metrics["latest_zscore"]
    if live_zscore is None or abs(live_zscore) < runtime_config["entry_zscore"]:
        return None
    if live_metrics["coint_flag"] != 1:
        return None
    if not (min_half_life <= live_metrics["half_life"] <= max_half_life):
        return None

    hedge_ratio = abs(float(live_metrics["hedge_ratio"]))
    if hedge_ratio <= 0:
        return None

    direction_1 = "Short" if live_zscore > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"
    leverage = float(runtime_config["leverage"])
    capital_base = float(runtime_config["paper_balance"]) * float(runtime_config["capital_per_trade_pct"])
    notional_budget = capital_base * leverage

    meta_1 = get_instrument_meta(candidate_row["sym_1"])
    meta_2 = get_instrument_meta(candidate_row["sym_2"])
    if not meta_1 or not meta_2:
        return None

    qty_step_1 = float(meta_1["lotSizeFilter"]["qtyStep"])
    qty_step_2 = float(meta_2["lotSizeFilter"]["qtyStep"])
    min_notional_1 = float(meta_1["lotSizeFilter"].get("minNotionalValue", 5))
    min_notional_2 = float(meta_2["lotSizeFilter"].get("minNotionalValue", 5))

    slippage_bps = float(runtime_config["slippage_bps"])
    entry_price_1 = get_executable_price(candidate_row["sym_1"], direction_1, "open", slippage_bps)
    entry_price_2 = get_executable_price(candidate_row["sym_2"], direction_2, "open", slippage_bps)
    if entry_price_1 is None or entry_price_2 is None:
        return None

    denominator = entry_price_1 + (hedge_ratio * entry_price_2)
    if denominator <= 0:
        return None

    quantity_1 = round_quantity(notional_budget / denominator, qty_step_1)
    quantity_2 = round_quantity(quantity_1 * hedge_ratio, qty_step_2)
    if quantity_1 <= 0 or quantity_2 <= 0:
        return None

    notional_1 = quantity_1 * entry_price_1
    notional_2 = quantity_2 * entry_price_2
    if notional_1 < min_notional_1 or notional_2 < min_notional_2:
        return None

    return {
        "opened_at": datetime.utcnow().isoformat(),
        "ticker_1": candidate_row["sym_1"],
        "ticker_2": candidate_row["sym_2"],
        "direction_1": direction_1,
        "direction_2": direction_2,
        "entry_zscore": float(live_zscore),
        "hedge_ratio": float(live_metrics["hedge_ratio"]),
        "intercept": float(live_metrics["intercept"]),
        "quantity_1": float(quantity_1),
        "quantity_2": float(quantity_2),
        "entry_price_1": float(entry_price_1),
        "entry_price_2": float(entry_price_2),
        "capital_base": float(capital_base),
        "fee_rate": float(runtime_config["fee_rate"]),
        "slippage_bps": slippage_bps,
        "max_holding_bars": int(runtime_config["max_holding_bars"]),
    }


def evaluate_position(position):
    current_metrics = get_latest_pair_metrics(position["ticker_1"], position["ticker_2"])
    if current_metrics is None:
        return None

    exit_price_1 = get_executable_price(
        position["ticker_1"],
        position["direction_1"],
        "close",
        position["slippage_bps"],
    )
    exit_price_2 = get_executable_price(
        position["ticker_2"],
        position["direction_2"],
        "close",
        position["slippage_bps"],
    )
    if exit_price_1 is None or exit_price_2 is None:
        return None

    leg_1_pnl = calculate_leg_pnl(
        position["direction_1"],
        position["quantity_1"],
        position["entry_price_1"],
        exit_price_1,
    )
    leg_2_pnl = calculate_leg_pnl(
        position["direction_2"],
        position["quantity_2"],
        position["entry_price_2"],
        exit_price_2,
    )
    gross_pnl = leg_1_pnl + leg_2_pnl

    entry_notional = (
        position["quantity_1"] * position["entry_price_1"]
        + position["quantity_2"] * position["entry_price_2"]
    )
    exit_notional = (
        position["quantity_1"] * exit_price_1
        + position["quantity_2"] * exit_price_2
    )
    fees_paid = (entry_notional + exit_notional) * position["fee_rate"]
    net_pnl = gross_pnl - fees_paid
    return_pct = (net_pnl / position["capital_base"]) * 100 if position["capital_base"] else 0

    opened_at = datetime.fromisoformat(position["opened_at"])
    age_seconds = max((datetime.utcnow() - opened_at).total_seconds(), 0)
    holding_bars = age_seconds / (float(timeframe) * 60)

    return {
        "exit_price_1": exit_price_1,
        "exit_price_2": exit_price_2,
        "gross_pnl": gross_pnl,
        "fees_paid": fees_paid,
        "net_pnl": net_pnl,
        "return_pct": return_pct,
        "current_zscore": float(current_metrics["latest_zscore"]),
        "holding_bars": holding_bars,
        "coint_flag": int(current_metrics["coint_flag"]),
        "half_life": float(current_metrics["half_life"]),
    }


def should_close_position(position, runtime_config, evaluation):
    current_zscore = abs(evaluation["current_zscore"])
    if evaluation["coint_flag"] != 1:
        return "model_breakdown"
    if not (min_half_life <= evaluation["half_life"] <= max_half_life):
        return "model_breakdown"
    if current_zscore <= float(runtime_config["exit_zscore"]):
        return "mean_reversion"
    if current_zscore >= float(runtime_config["stop_zscore"]):
        return "zscore_stop"
    if evaluation["holding_bars"] >= position["max_holding_bars"]:
        return "time_stop"
    return None


def monitor_paper_position(position, runtime_config):
    while True:
        time.sleep(60)
        evaluation = evaluate_position(position)
        if evaluation is None:
            continue

        if int(time.time()) % 900 < 60:
            pnl_message = (
                f"{position['ticker_1']} / {position['ticker_2']} | "
                f"z={evaluation['current_zscore']:.2f} | "
                f"net={evaluation['net_pnl']:.2f} USDT | "
                f"roe={evaluation['return_pct']:.2f}%"
            )
            asyncio.run(send_telegram_message(pnl_message))

        exit_reason = should_close_position(position, runtime_config, evaluation)
        if not exit_reason:
            continue

        trade_record = {
            "opened_at": position["opened_at"],
            "closed_at": datetime.utcnow().isoformat(),
            "ticker_1": position["ticker_1"],
            "ticker_2": position["ticker_2"],
            "direction_1": position["direction_1"],
            "direction_2": position["direction_2"],
            "entry_zscore": position["entry_zscore"],
            "exit_zscore": evaluation["current_zscore"],
            "exit_reason": exit_reason,
            "hedge_ratio": position["hedge_ratio"],
            "intercept": position["intercept"],
            "quantity_1": position["quantity_1"],
            "quantity_2": position["quantity_2"],
            "entry_price_1": position["entry_price_1"],
            "entry_price_2": position["entry_price_2"],
            "exit_price_1": evaluation["exit_price_1"],
            "exit_price_2": evaluation["exit_price_2"],
            "gross_pnl": evaluation["gross_pnl"],
            "fees_paid": evaluation["fees_paid"],
            "net_pnl": evaluation["net_pnl"],
            "return_pct": evaluation["return_pct"],
        }
        append_trade_log(trade_record)

        message = (
            f"Paper trade closed: {position['ticker_1']} / {position['ticker_2']} | "
            f"reason={exit_reason} | net={evaluation['net_pnl']:.2f} USDT | "
            f"roe={evaluation['return_pct']:.2f}%"
        )
        asyncio.run(send_telegram_message(message))

        if exit_reason != "mean_reversion" or evaluation["net_pnl"] <= 0:
            return [position["ticker_1"], position["ticker_2"]]
        return []


def pick_pair(bad_pairs):
    runtime_config = load_runtime_config()
    if not Path("2_cointegrated_pairs.xlsx").exists():
        return []

    df = pd.read_excel("2_cointegrated_pairs.xlsx")
    if df.empty:
        return []

    if "score" in df.columns:
        df = df.sort_values(by="score", ascending=False)

    candidates = []
    for _, row in df.head(top_pairs_to_scan).iterrows():
        if row["sym_1"] in bad_pairs or row["sym_2"] in bad_pairs:
            continue

        live_metrics = get_latest_pair_metrics(row["sym_1"], row["sym_2"])
        if live_metrics is None or live_metrics["latest_zscore"] is None:
            continue
        if live_metrics["coint_flag"] != 1:
            continue

        if not (min_half_life <= live_metrics["half_life"] <= max_half_life):
            continue

        if abs(live_metrics["latest_zscore"]) < float(runtime_config["entry_zscore"]):
            continue

        candidate_score = abs(live_metrics["latest_zscore"]) + float(row.get("score", 0))
        candidates.append((candidate_score, row.to_dict()))

    if not candidates:
        return []

    candidates.sort(key=lambda item: item[0], reverse=True)

    for _score, candidate in candidates:
        position = build_position_from_candidate(candidate, runtime_config)
        if position is None:
            continue

        asyncio.run(
            send_telegram_message(
                (
                    f"Paper trade opened: {position['ticker_1']} / {position['ticker_2']} | "
                    f"{position['direction_1']} / {position['direction_2']} | "
                    f"z={position['entry_zscore']:.2f}"
                )
            )
        )
        return monitor_paper_position(position, runtime_config)

    return []
