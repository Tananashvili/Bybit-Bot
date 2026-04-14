import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from Execution.config_execution_api import BACKTEST_TRADES_PATH, load_runtime_config
from Execution.func_execution_calls import get_instrument_meta
from Execution.helping_functions import round_quantity
from Strategy.config_strategy_api import (
    max_abs_hedge_ratio,
    max_entry_zscore,
    max_half_life,
    min_abs_hedge_ratio,
    min_half_life,
    top_pairs_to_scan,
    z_score_window,
)
from Strategy.func_cointegration import get_cointegrated_pairs
from Strategy.func_get_symbols import get_tradeable_symbols
from Strategy.func_price_klines import get_price_klines
from Strategy.func_prices_json import store_price_history
from Strategy.helping_functions import calculate_entry_band_score, filter_data, pick_best_pair
from pair_stats import calculate_pair_metrics

BACKTEST_PRICE_LIST_PATH = Path("backtest_price_list.json")
BACKTEST_PAIR_FILE_PATH = Path("backtest_cointegrated_pairs.xlsx")


def get_kline_frame(symbol):
    raw_klines = get_price_klines(symbol)
    if not raw_klines:
        return pd.DataFrame(columns=["timestamp", "close"])

    frame = pd.DataFrame(
        [{"timestamp": row[0], "close": row[-1]} for row in raw_klines]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
    frame["close"] = frame["close"].astype("float64")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def calculate_backtest_price(price, direction, slippage_bps, action):
    slippage_multiplier = 1 + (slippage_bps / 10000)
    if (direction == "Long" and action == "open") or (direction == "Short" and action == "close"):
        return price * slippage_multiplier
    return price / slippage_multiplier


def get_open_slots(state, runtime_config):
    return max(int(runtime_config["max_open_positions"]) - len(state["active_positions"]), 0)


def get_active_symbols(state):
    active_symbols = set()
    for position in state["active_positions"]:
        active_symbols.add(position["ticker_1"])
        active_symbols.add(position["ticker_2"])
    return active_symbols


def get_allocation_per_new_position(state, runtime_config):
    open_slots = get_open_slots(state, runtime_config)
    if open_slots <= 0:
        return 0.0

    allocatable_cash = float(state["cash_balance"]) * (1 - float(runtime_config["cash_reserve_pct"]))
    return max(allocatable_cash / open_slots, 0.0)


def update_profit_lock(position, runtime_config, evaluation):
    peak_return_pct = max(
        float(position.get("peak_return_pct", evaluation["return_pct"])),
        float(evaluation["return_pct"]),
    )
    position["peak_return_pct"] = peak_return_pct

    activation_pct = float(runtime_config["profit_lock_activation_pct"])
    keep_ratio = float(runtime_config["profit_lock_keep_ratio"])
    min_return_pct = float(runtime_config["profit_lock_min_return_pct"])

    if peak_return_pct >= activation_pct:
        position["profit_lock_active"] = True
        position["profit_lock_floor_pct"] = max(
            min_return_pct,
            peak_return_pct * keep_ratio,
        )
    else:
        position["profit_lock_active"] = False
        position["profit_lock_floor_pct"] = 0.0


def build_pair_history(pair_row, lookback_bars):
    frame_1 = get_kline_frame(pair_row["sym_1"])
    frame_2 = get_kline_frame(pair_row["sym_2"])
    if frame_1.empty or frame_2.empty:
        return None

    merged = frame_1.merge(frame_2, on="timestamp", suffixes=("_1", "_2"))
    merged = merged.sort_values("timestamp").reset_index(drop=True)
    if len(merged) <= lookback_bars:
        return None

    return {
        "pair_key": f"{pair_row['sym_1']}__{pair_row['sym_2']}",
        "pair_row": pair_row,
        "score": float(pair_row.get("score", 0.0)),
        "frame": merged,
        "timestamp_to_index": {
            timestamp: index
            for index, timestamp in enumerate(merged["timestamp"])
        },
    }


def build_snapshot(pair_history, row_index, lookback_bars):
    if row_index is None or row_index < lookback_bars:
        return None

    history = pair_history["frame"].iloc[row_index - lookback_bars:row_index + 1]
    metrics = calculate_pair_metrics(
        history["close_1"].tolist(),
        history["close_2"].tolist(),
        z_score_window,
    )

    latest_row = history.iloc[-1]
    pair_row = pair_history["pair_row"]
    return {
        "pair_key": pair_history["pair_key"],
        "pair_row": pair_row,
        "timestamp": latest_row["timestamp"].to_pydatetime(),
        "row_index": int(row_index),
        "score": pair_history["score"],
        "price_1": float(latest_row["close_1"]),
        "price_2": float(latest_row["close_2"]),
        "metrics": metrics,
    }


def get_instrument_constraints(symbol, cache):
    if symbol not in cache:
        meta = get_instrument_meta(symbol)
        if not meta:
            return None

        lot_filter = meta.get("lotSizeFilter", {})
        cache[symbol] = {
            "qty_step": float(lot_filter.get("qtyStep", 0) or 0),
            "min_notional": float(lot_filter.get("minNotionalValue", 5) or 5),
        }

    return cache[symbol]


def build_backtest_position(snapshot, runtime_config, state, instrument_cache):
    metrics = snapshot["metrics"]
    if metrics["latest_zscore"] is None:
        return None
    if not float(runtime_config["entry_zscore"]) <= abs(float(metrics["latest_zscore"])) <= max_entry_zscore:
        return None

    reserved_capital = get_allocation_per_new_position(state, runtime_config)
    if reserved_capital <= 0:
        return None

    raw_hedge_ratio = float(metrics["hedge_ratio"])
    if raw_hedge_ratio <= 0:
        return None

    hedge_ratio = abs(raw_hedge_ratio)
    if not (min_abs_hedge_ratio <= hedge_ratio <= max_abs_hedge_ratio):
        return None

    constraints_1 = get_instrument_constraints(snapshot["pair_row"]["sym_1"], instrument_cache)
    constraints_2 = get_instrument_constraints(snapshot["pair_row"]["sym_2"], instrument_cache)
    if not constraints_1 or not constraints_2:
        return None

    direction_1 = "Short" if metrics["latest_zscore"] > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"
    leverage = float(runtime_config["leverage"])

    entry_price_1 = calculate_backtest_price(
        snapshot["price_1"],
        direction_1,
        float(runtime_config["open_slippage_bps"]),
        "open",
    )
    entry_price_2 = calculate_backtest_price(
        snapshot["price_2"],
        direction_2,
        float(runtime_config["open_slippage_bps"]),
        "open",
    )

    denominator = entry_price_1 + (hedge_ratio * entry_price_2)
    if denominator <= 0:
        return None

    notional_budget = reserved_capital * leverage
    quantity_1 = round_quantity(
        notional_budget / denominator,
        constraints_1["qty_step"],
    )
    quantity_2 = round_quantity(
        quantity_1 * hedge_ratio,
        constraints_2["qty_step"],
    )
    if quantity_1 <= 0 or quantity_2 <= 0:
        return None

    notional_1 = quantity_1 * entry_price_1
    notional_2 = quantity_2 * entry_price_2
    if notional_1 < constraints_1["min_notional"] or notional_2 < constraints_2["min_notional"]:
        return None

    open_fee = (notional_1 + notional_2) * float(runtime_config["open_fee_rate"])
    if (reserved_capital + open_fee) >= float(state["cash_balance"]):
        return None

    return {
        "pair_key": snapshot["pair_key"],
        "opened_at": snapshot["timestamp"].isoformat(),
        "opened_index": snapshot["row_index"],
        "ticker_1": snapshot["pair_row"]["sym_1"],
        "ticker_2": snapshot["pair_row"]["sym_2"],
        "direction_1": direction_1,
        "direction_2": direction_2,
        "entry_zscore": float(metrics["latest_zscore"]),
        "hedge_ratio": float(metrics["hedge_ratio"]),
        "intercept": float(metrics["intercept"]),
        "quantity_1": float(quantity_1),
        "quantity_2": float(quantity_2),
        "entry_price_1": float(entry_price_1),
        "entry_price_2": float(entry_price_2),
        "reserved_capital": float(reserved_capital),
        "open_fee": float(open_fee),
        "peak_return_pct": 0.0,
        "profit_lock_active": False,
        "profit_lock_floor_pct": 0.0,
    }


def evaluate_backtest_position(position, snapshot, runtime_config):
    metrics = snapshot["metrics"]

    exit_price_1 = calculate_backtest_price(
        snapshot["price_1"],
        position["direction_1"],
        float(runtime_config["close_slippage_bps"]),
        "close",
    )
    exit_price_2 = calculate_backtest_price(
        snapshot["price_2"],
        position["direction_2"],
        float(runtime_config["close_slippage_bps"]),
        "close",
    )

    leg_1_pnl = (
        position["quantity_1"] * (exit_price_1 - position["entry_price_1"])
        if position["direction_1"] == "Long"
        else position["quantity_1"] * (position["entry_price_1"] - exit_price_1)
    )
    leg_2_pnl = (
        position["quantity_2"] * (exit_price_2 - position["entry_price_2"])
        if position["direction_2"] == "Long"
        else position["quantity_2"] * (position["entry_price_2"] - exit_price_2)
    )
    gross_pnl = leg_1_pnl + leg_2_pnl

    exit_notional = (
        position["quantity_1"] * exit_price_1
        + position["quantity_2"] * exit_price_2
    )
    close_fee = exit_notional * float(runtime_config["close_fee_rate"])
    fees_paid = position["open_fee"] + close_fee
    net_pnl = gross_pnl - fees_paid
    return_pct = (net_pnl / position["reserved_capital"]) * 100 if position["reserved_capital"] else 0
    live_value = position["reserved_capital"] + gross_pnl - close_fee

    return {
        "timestamp": snapshot["timestamp"],
        "exit_price_1": float(exit_price_1),
        "exit_price_2": float(exit_price_2),
        "gross_pnl": float(gross_pnl),
        "close_fee": float(close_fee),
        "fees_paid": float(fees_paid),
        "net_pnl": float(net_pnl),
        "return_pct": float(return_pct),
        "current_zscore": float(metrics["latest_zscore"]) if metrics["latest_zscore"] is not None else 0.0,
        "holding_bars": int(snapshot["row_index"] - position["opened_index"]),
        "coint_flag": int(metrics["coint_flag"]),
        "half_life": float(metrics["half_life"]),
        "live_value": float(live_value),
    }


def should_close_position(runtime_config, evaluation):
    current_zscore = abs(evaluation["current_zscore"])
    if evaluation["coint_flag"] != 1:
        return "model_breakdown"
    if not (min_half_life <= evaluation["half_life"] <= max_half_life):
        return "model_breakdown"
    if current_zscore <= float(runtime_config["exit_zscore"]):
        return "mean_reversion"
    if (
        evaluation["profit_lock_active"]
        and evaluation["return_pct"] <= evaluation["profit_lock_floor_pct"]
    ):
        return "profit_lock_stop"
    if current_zscore >= float(runtime_config["stop_zscore"]):
        return "zscore_stop"
    if evaluation["holding_bars"] >= int(runtime_config["max_holding_bars"]):
        return "time_stop"
    return None


def close_backtest_position(position, evaluation, exit_reason, state):
    state["cash_balance"] += (
        position["reserved_capital"]
        + evaluation["gross_pnl"]
        - evaluation["close_fee"]
    )

    return {
        "opened_at": position["opened_at"],
        "closed_at": evaluation["timestamp"].isoformat(),
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
        "peak_return_pct": position.get("peak_return_pct", 0.0),
        "profit_lock_floor_pct": position.get("profit_lock_floor_pct", 0.0),
    }


def sync_active_positions(state, runtime_config, pair_histories, current_timestamp, lookback_bars, trades):
    remaining_positions = []

    for position in state["active_positions"]:
        pair_history = pair_histories[position["pair_key"]]
        row_index = pair_history["timestamp_to_index"].get(current_timestamp)
        snapshot = build_snapshot(pair_history, row_index, lookback_bars)
        if snapshot is None:
            remaining_positions.append(position)
            continue

        evaluation = evaluate_backtest_position(position, snapshot, runtime_config)
        update_profit_lock(position, runtime_config, evaluation)
        evaluation["profit_lock_active"] = bool(position.get("profit_lock_active"))
        evaluation["profit_lock_floor_pct"] = float(position.get("profit_lock_floor_pct", 0.0))
        exit_reason = should_close_position(runtime_config, evaluation)
        if not exit_reason:
            remaining_positions.append(position)
            continue

        trades.append(close_backtest_position(position, evaluation, exit_reason, state))

    state["active_positions"] = remaining_positions


def build_candidate_list(state, runtime_config, pair_histories, current_timestamp, lookback_bars):
    blocked_symbols = get_active_symbols(state)
    candidates = []

    for pair_history in pair_histories.values():
        pair_row = pair_history["pair_row"]
        if pair_row["sym_1"] in blocked_symbols or pair_row["sym_2"] in blocked_symbols:
            continue

        row_index = pair_history["timestamp_to_index"].get(current_timestamp)
        snapshot = build_snapshot(pair_history, row_index, lookback_bars)
        if snapshot is None:
            continue

        metrics = snapshot["metrics"]
        if metrics["latest_zscore"] is None or metrics["coint_flag"] != 1:
            continue
        if not (min_half_life <= metrics["half_life"] <= max_half_life):
            continue
        abs_zscore = abs(float(metrics["latest_zscore"]))
        if not float(runtime_config["entry_zscore"]) <= abs_zscore <= max_entry_zscore:
            continue
        if float(metrics["hedge_ratio"]) <= 0:
            continue
        if not (min_abs_hedge_ratio <= abs(float(metrics["hedge_ratio"])) <= max_abs_hedge_ratio):
            continue

        snapshot["candidate_score"] = (
            calculate_entry_band_score(abs_zscore)
            + float(snapshot["score"])
        )
        candidates.append(snapshot)

    candidates.sort(key=lambda item: item["candidate_score"], reverse=True)
    return candidates


def open_new_positions(state, runtime_config, pair_histories, current_timestamp, lookback_bars, instrument_cache):
    while get_open_slots(state, runtime_config) > 0:
        candidates = build_candidate_list(state, runtime_config, pair_histories, current_timestamp, lookback_bars)
        if not candidates:
            break

        position_opened = False
        for candidate in candidates:
            position = build_backtest_position(candidate, runtime_config, state, instrument_cache)
            if position is None:
                continue

            state["cash_balance"] -= position["reserved_capital"] + position["open_fee"]
            state["active_positions"].append(position)
            state["max_concurrent_positions_seen"] = max(
                state["max_concurrent_positions_seen"],
                len(state["active_positions"]),
            )
            position_opened = True
            break

        if not position_opened:
            break


def close_remaining_positions(state, runtime_config, pair_histories, lookback_bars, trades):
    for position in list(state["active_positions"]):
        pair_history = pair_histories[position["pair_key"]]
        last_index = len(pair_history["frame"]) - 1
        snapshot = build_snapshot(pair_history, last_index, lookback_bars)
        if snapshot is None:
            continue

        evaluation = evaluate_backtest_position(position, snapshot, runtime_config)
        update_profit_lock(position, runtime_config, evaluation)
        trades.append(close_backtest_position(position, evaluation, "end_of_test", state))

    state["active_positions"] = []


def refresh_candidate_pairs():
    symbols = get_tradeable_symbols()
    if symbols:
        store_price_history(symbols, output_path=BACKTEST_PRICE_LIST_PATH)

    if not BACKTEST_PRICE_LIST_PATH.exists():
        return

    with BACKTEST_PRICE_LIST_PATH.open("r", encoding="utf-8") as json_file:
        price_data = json.load(json_file)

    coint_pairs = get_cointegrated_pairs(price_data, [])
    filter_data(coint_pairs, output_path=BACKTEST_PAIR_FILE_PATH)
    pick_best_pair(input_path=BACKTEST_PAIR_FILE_PATH, output_path=BACKTEST_PAIR_FILE_PATH)


def write_backtest_results(trades):
    if not trades:
        if BACKTEST_TRADES_PATH.exists():
            BACKTEST_TRADES_PATH.unlink()
        return

    with BACKTEST_TRADES_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(trades[0].keys()))
        writer.writeheader()
        writer.writerows(trades)


def run_portfolio_backtest(ranked_pairs, runtime_config):
    lookback_bars = max(int(runtime_config["backtest_lookback_bars"]), z_score_window + 5)
    pair_histories = {}
    global_timestamps = set()

    for _, pair_row in ranked_pairs.head(min(top_pairs_to_scan, int(runtime_config["backtest_top_pairs"]))).iterrows():
        pair_history = build_pair_history(pair_row.to_dict(), lookback_bars)
        if pair_history is None:
            continue

        pair_histories[pair_history["pair_key"]] = pair_history
        global_timestamps.update(pair_history["frame"]["timestamp"].iloc[lookback_bars:].tolist())

    if not pair_histories or not global_timestamps:
        return [], {
            "total_trades": 0,
            "total_net_pnl": 0.0,
            "starting_balance": float(runtime_config["paper_balance"]),
            "ending_balance": float(runtime_config["paper_balance"]),
            "return_pct": 0.0,
            "win_rate": 0.0,
            "max_concurrent_positions": 0,
            "generated_at": datetime.utcnow().isoformat(),
        }

    state = {
        "cash_balance": float(runtime_config["paper_balance"]),
        "active_positions": [],
        "max_concurrent_positions_seen": 0,
    }
    trades = []
    instrument_cache = {}

    for current_timestamp in sorted(global_timestamps):
        sync_active_positions(
            state,
            runtime_config,
            pair_histories,
            current_timestamp,
            lookback_bars,
            trades,
        )
        open_new_positions(
            state,
            runtime_config,
            pair_histories,
            current_timestamp,
            lookback_bars,
            instrument_cache,
        )

    close_remaining_positions(
        state,
        runtime_config,
        pair_histories,
        lookback_bars,
        trades,
    )

    total_net_pnl = sum(trade["net_pnl"] for trade in trades)
    ending_balance = float(state["cash_balance"])
    win_rate = (
        sum(1 for trade in trades if trade["net_pnl"] > 0) / len(trades) * 100
        if trades
        else 0.0
    )
    summary = {
        "total_trades": len(trades),
        "total_net_pnl": float(total_net_pnl),
        "starting_balance": float(runtime_config["paper_balance"]),
        "ending_balance": ending_balance,
        "return_pct": (
            ((ending_balance / float(runtime_config["paper_balance"])) - 1) * 100
            if float(runtime_config["paper_balance"])
            else 0.0
        ),
        "win_rate": float(win_rate),
        "max_concurrent_positions": int(state["max_concurrent_positions_seen"]),
        "generated_at": datetime.utcnow().isoformat(),
    }
    return trades, summary


def main():
    runtime_config = load_runtime_config()
    refresh_candidate_pairs()

    if not BACKTEST_PAIR_FILE_PATH.exists():
        print("No candidate pairs file found.")
        return

    ranked_pairs = pd.read_excel(BACKTEST_PAIR_FILE_PATH)
    if ranked_pairs.empty:
        print("No candidate pairs found.")
        return

    if "score" in ranked_pairs.columns:
        ranked_pairs = ranked_pairs.sort_values(by="score", ascending=False)

    trades, summary = run_portfolio_backtest(ranked_pairs, runtime_config)
    write_backtest_results(trades)
    print(json.dumps(summary, indent=4))


if __name__ == "__main__":
    main()
