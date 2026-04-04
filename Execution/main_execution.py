import asyncio
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telegram import Bot

from Execution.config_execution_api import (
    PAPER_TRADES_PATH,
    load_paper_state,
    load_runtime_config,
    save_paper_state,
    timeframe,
)
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


def get_raw_book_price(ticker, direction, action):
    snapshot = get_ticker_snapshot(ticker)
    try:
        bid_price = float(snapshot["bid1Price"])
        ask_price = float(snapshot["ask1Price"])
    except (KeyError, TypeError, ValueError):
        return None

    if action == "open":
        # Simulate passive limit orders: buy on the bid, sell on the ask.
        return bid_price if direction == "Long" else ask_price

    # Simulate exit at the immediately executable side.
    return bid_price if direction == "Long" else ask_price


def apply_slippage(price, direction, action, slippage_bps):
    slippage_multiplier = 1 + (slippage_bps / 10000)
    if (direction == "Long" and action == "open") or (direction == "Short" and action == "close"):
        return price * slippage_multiplier
    return price / slippage_multiplier


def get_execution_price(ticker, direction, action, slippage_bps):
    raw_price = get_raw_book_price(ticker, direction, action)
    if raw_price is None:
        return None
    return apply_slippage(raw_price, direction, action, slippage_bps)


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
        "reserved_capital",
        "quantity_1",
        "quantity_2",
        "entry_price_1",
        "entry_price_2",
        "exit_price_1",
        "exit_price_2",
        "gross_pnl",
        "open_fee",
        "close_fee",
        "fees_paid",
        "net_pnl",
        "return_pct",
    ]

    with PAPER_TRADES_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def get_active_symbols(state):
    active_symbols = set()
    for position in state["active_positions"]:
        active_symbols.add(position["ticker_1"])
        active_symbols.add(position["ticker_2"])
    return active_symbols


def get_open_slots(state, runtime_config):
    return max(int(runtime_config["max_open_positions"]) - len(state["active_positions"]), 0)


def get_allocation_per_new_position(state, runtime_config):
    open_slots = get_open_slots(state, runtime_config)
    if open_slots <= 0:
        return 0.0

    allocatable_cash = float(state["cash_balance"]) * (1 - float(runtime_config["cash_reserve_pct"]))
    return max(allocatable_cash / open_slots, 0.0)


def build_position_from_candidate(candidate, runtime_config, state):
    live_metrics = candidate["live_metrics"]
    candidate_row = candidate["row"]

    if live_metrics["latest_zscore"] is None:
        return None

    reserved_capital = get_allocation_per_new_position(state, runtime_config)
    if reserved_capital <= 0:
        return None

    hedge_ratio = abs(float(live_metrics["hedge_ratio"]))
    if hedge_ratio <= 0:
        return None

    direction_1 = "Short" if live_metrics["latest_zscore"] > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"
    leverage = float(runtime_config["leverage"])
    notional_budget = reserved_capital * leverage

    meta_1 = get_instrument_meta(candidate_row["sym_1"])
    meta_2 = get_instrument_meta(candidate_row["sym_2"])
    if not meta_1 or not meta_2:
        return None

    qty_step_1 = float(meta_1["lotSizeFilter"]["qtyStep"])
    qty_step_2 = float(meta_2["lotSizeFilter"]["qtyStep"])
    min_notional_1 = float(meta_1["lotSizeFilter"].get("minNotionalValue", 5))
    min_notional_2 = float(meta_2["lotSizeFilter"].get("minNotionalValue", 5))

    entry_price_1 = get_execution_price(
        candidate_row["sym_1"],
        direction_1,
        "open",
        float(runtime_config["open_slippage_bps"]),
    )
    entry_price_2 = get_execution_price(
        candidate_row["sym_2"],
        direction_2,
        "open",
        float(runtime_config["open_slippage_bps"]),
    )
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

    open_fee = (notional_1 + notional_2) * float(runtime_config["open_fee_rate"])
    if (reserved_capital + open_fee) >= float(state["cash_balance"]):
        return None

    return {
        "opened_at": datetime.utcnow().isoformat(),
        "ticker_1": candidate_row["sym_1"],
        "ticker_2": candidate_row["sym_2"],
        "direction_1": direction_1,
        "direction_2": direction_2,
        "entry_zscore": float(live_metrics["latest_zscore"]),
        "hedge_ratio": float(live_metrics["hedge_ratio"]),
        "intercept": float(live_metrics["intercept"]),
        "quantity_1": float(quantity_1),
        "quantity_2": float(quantity_2),
        "entry_price_1": float(entry_price_1),
        "entry_price_2": float(entry_price_2),
        "reserved_capital": float(reserved_capital),
        "open_fee": float(open_fee),
        "open_notional": float(notional_1 + notional_2),
    }


def evaluate_position(position, runtime_config):
    live_metrics = get_latest_pair_metrics(
        position["ticker_1"],
        position["ticker_2"],
        use_live_mark=True,
    )
    model_metrics = get_latest_pair_metrics(
        position["ticker_1"],
        position["ticker_2"],
        use_live_mark=False,
    )
    if live_metrics is None or model_metrics is None:
        return None

    exit_price_1 = get_execution_price(
        position["ticker_1"],
        position["direction_1"],
        "close",
        float(runtime_config["close_slippage_bps"]),
    )
    exit_price_2 = get_execution_price(
        position["ticker_2"],
        position["direction_2"],
        "close",
        float(runtime_config["close_slippage_bps"]),
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

    exit_notional = (
        position["quantity_1"] * exit_price_1
        + position["quantity_2"] * exit_price_2
    )
    close_fee = exit_notional * float(runtime_config["close_fee_rate"])
    total_fees = position["open_fee"] + close_fee
    net_pnl = gross_pnl - total_fees
    return_pct = (net_pnl / position["reserved_capital"]) * 100 if position["reserved_capital"] else 0

    opened_at = datetime.fromisoformat(position["opened_at"])
    age_seconds = max((datetime.utcnow() - opened_at).total_seconds(), 0)
    holding_bars = age_seconds / (float(timeframe) * 60)

    # Open fee has already left cash balance, so live value only subtracts the estimated closing fee.
    live_value = position["reserved_capital"] + gross_pnl - close_fee

    return {
        "exit_price_1": exit_price_1,
        "exit_price_2": exit_price_2,
        "gross_pnl": gross_pnl,
        "close_fee": close_fee,
        "fees_paid": total_fees,
        "net_pnl": net_pnl,
        "return_pct": return_pct,
        "current_zscore": float(live_metrics["latest_zscore"]),
        "holding_bars": holding_bars,
        "model_coint_flag": int(model_metrics["coint_flag"]),
        "model_half_life": float(model_metrics["half_life"]),
        "model_p_value": float(model_metrics["p_value"]),
        "live_value": live_value,
    }


def should_close_position(position, runtime_config, evaluation):
    current_zscore = abs(evaluation["current_zscore"])
    if evaluation["model_coint_flag"] != 1:
        return "model_breakdown_coint"
    if not (min_half_life <= evaluation["model_half_life"] <= max_half_life):
        return "model_breakdown_half_life"
    if current_zscore <= float(runtime_config["exit_zscore"]):
        return "mean_reversion"
    if current_zscore >= float(runtime_config["stop_zscore"]):
        return "zscore_stop"
    if evaluation["holding_bars"] >= int(runtime_config["max_holding_bars"]):
        return "time_stop"
    return None


def close_position(position, evaluation, exit_reason, state):
    state["cash_balance"] += (
        position["reserved_capital"]
        + evaluation["gross_pnl"]
        - evaluation["close_fee"]
    )

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
        "reserved_capital": position["reserved_capital"],
        "quantity_1": position["quantity_1"],
        "quantity_2": position["quantity_2"],
        "entry_price_1": position["entry_price_1"],
        "entry_price_2": position["entry_price_2"],
        "exit_price_1": evaluation["exit_price_1"],
        "exit_price_2": evaluation["exit_price_2"],
        "gross_pnl": evaluation["gross_pnl"],
        "open_fee": position["open_fee"],
        "close_fee": evaluation["close_fee"],
        "fees_paid": evaluation["fees_paid"],
        "net_pnl": evaluation["net_pnl"],
        "return_pct": evaluation["return_pct"],
    }
    append_trade_log(trade_record)

    message = (
        f"Paper trade closed: {position['ticker_1']} / {position['ticker_2']} | "
        f"reason={exit_reason} | net={evaluation['net_pnl']:.2f} USDT | "
        f"cash={state['cash_balance']:.2f}"
    )
    if exit_reason.startswith("model_breakdown"):
        message += (
            f" | p={evaluation['model_p_value']:.4f} "
            f"| hl={evaluation['model_half_life']:.2f}"
        )
    asyncio.run(send_telegram_message(message))


def sync_active_positions(state, runtime_config, bad_pairs):
    remaining_positions = []

    for position in state["active_positions"]:
        evaluation = evaluate_position(position, runtime_config)
        if evaluation is None:
            remaining_positions.append(position)
            continue

        exit_reason = should_close_position(position, runtime_config, evaluation)
        if not exit_reason:
            remaining_positions.append(position)
            continue

        close_position(position, evaluation, exit_reason, state)
        if exit_reason != "mean_reversion" or evaluation["net_pnl"] <= 0:
            bad_pairs.extend([position["ticker_1"], position["ticker_2"]])

    state["active_positions"] = remaining_positions
    return list(dict.fromkeys(bad_pairs))


def build_candidate_list(state, runtime_config, bad_pairs):
    if not Path("2_cointegrated_pairs.xlsx").exists():
        return []

    df = pd.read_excel("2_cointegrated_pairs.xlsx")
    if df.empty:
        return []

    if "score" in df.columns:
        df = df.sort_values(by="score", ascending=False)

    blocked_symbols = get_active_symbols(state)
    candidates = []

    for _, row in df.head(top_pairs_to_scan).iterrows():
        row_data = row.to_dict()
        if row_data["sym_1"] in bad_pairs or row_data["sym_2"] in bad_pairs:
            continue
        if row_data["sym_1"] in blocked_symbols or row_data["sym_2"] in blocked_symbols:
            continue

        live_metrics = get_latest_pair_metrics(
            row_data["sym_1"],
            row_data["sym_2"],
            use_live_mark=True,
        )
        model_metrics = get_latest_pair_metrics(
            row_data["sym_1"],
            row_data["sym_2"],
            use_live_mark=False,
        )
        if live_metrics is None or model_metrics is None or live_metrics["latest_zscore"] is None:
            continue
        if model_metrics["coint_flag"] != 1:
            continue
        if not (min_half_life <= model_metrics["half_life"] <= max_half_life):
            continue
        if abs(live_metrics["latest_zscore"]) < float(runtime_config["entry_zscore"]):
            continue

        candidate_score = abs(live_metrics["latest_zscore"]) + float(row_data.get("score", 0))
        candidates.append(
            {
                "score": candidate_score,
                "row": row_data,
                "live_metrics": live_metrics,
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def open_new_positions(state, runtime_config, bad_pairs):
    while get_open_slots(state, runtime_config) > 0:
        candidates = build_candidate_list(state, runtime_config, bad_pairs)
        if not candidates:
            break

        position_opened = False
        for candidate in candidates:
            position = build_position_from_candidate(candidate, runtime_config, state)
            if position is None:
                continue

            state["cash_balance"] -= position["reserved_capital"] + position["open_fee"]
            state["active_positions"].append(position)
            position_opened = True

            asyncio.run(
                send_telegram_message(
                    (
                        f"Paper trade opened: {position['ticker_1']} / {position['ticker_2']} | "
                        f"{position['direction_1']} / {position['direction_2']} | "
                        f"z={position['entry_zscore']:.2f} | "
                        f"reserved={position['reserved_capital']:.2f} | "
                        f"cash_left={state['cash_balance']:.2f}"
                    )
                )
            )
            break

        if not position_opened:
            break


def maybe_send_hourly_portfolio_update(state, runtime_config):
    now = datetime.utcnow()
    last_sent_at = state.get("last_portfolio_update_sent_at")
    if last_sent_at:
        last_sent_at = datetime.fromisoformat(last_sent_at)
        if now - last_sent_at < timedelta(minutes=int(runtime_config["portfolio_update_interval_minutes"])):
            return

    lines = [
        "Portfolio update",
        f"Cash balance: {state['cash_balance']:.2f} USDT",
        f"Active positions: {len(state['active_positions'])}",
    ]

    live_balance = float(state["cash_balance"])
    for position in state["active_positions"]:
        evaluation = evaluate_position(position, runtime_config)
        if evaluation is None:
            live_balance += position["reserved_capital"]
            lines.append(
                f"{position['ticker_1']}/{position['ticker_2']} | awaiting fresh data"
            )
            continue

        live_balance += evaluation["live_value"]
        lines.append(
            (
                f"{position['ticker_1']}/{position['ticker_2']} | "
                f"{position['direction_1']}/{position['direction_2']} | "
                f"z={evaluation['current_zscore']:.2f} | "
                f"net={evaluation['net_pnl']:.2f} | "
                f"roe={evaluation['return_pct']:.2f}%"
            )
        )

    lines.insert(1, f"Live balance: {live_balance:.2f} USDT")
    asyncio.run(send_telegram_message("\n".join(lines)))
    state["last_portfolio_update_sent_at"] = now.isoformat()


def run_portfolio_cycle(bad_pairs):
    runtime_config = load_runtime_config()
    state = load_paper_state()

    bad_pairs = sync_active_positions(state, runtime_config, bad_pairs)
    open_new_positions(state, runtime_config, bad_pairs)
    maybe_send_hourly_portfolio_update(state, runtime_config)

    save_paper_state(state)
    return bad_pairs
