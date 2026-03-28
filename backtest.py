import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from Execution.config_execution_api import BACKTEST_TRADES_PATH, load_runtime_config
from Strategy.config_strategy_api import (
    max_half_life,
    min_half_life,
    top_pairs_to_scan,
    z_score_window,
)
from Strategy.func_cointegration import get_cointegrated_pairs
from Strategy.func_get_symbols import get_tradeable_symbols
from Strategy.func_price_klines import get_price_klines
from Strategy.func_prices_json import store_price_history
from Strategy.helping_functions import filter_data, pick_best_pair
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


def calculate_backtest_prices(price, direction, slippage_bps, action):
    slippage_multiplier = 1 + (slippage_bps / 10000)
    if (direction == "Long" and action == "open") or (direction == "Short" and action == "close"):
        return price * slippage_multiplier
    return price / slippage_multiplier


def build_backtest_position(metrics, ticker_1, ticker_2, price_1, price_2, timestamp, bar_index, runtime_config):
    hedge_ratio = abs(float(metrics["hedge_ratio"]))
    if hedge_ratio <= 0:
        return None

    direction_1 = "Short" if metrics["latest_zscore"] > 0 else "Long"
    direction_2 = "Long" if direction_1 == "Short" else "Short"

    capital_base = float(runtime_config["paper_balance"]) * float(runtime_config["capital_per_trade_pct"])
    leverage = float(runtime_config["leverage"])
    notional_budget = capital_base * leverage
    denominator = price_1 + (hedge_ratio * price_2)
    if denominator <= 0:
        return None

    quantity_1 = notional_budget / denominator
    quantity_2 = quantity_1 * hedge_ratio

    entry_price_1 = calculate_backtest_prices(price_1, direction_1, float(runtime_config["slippage_bps"]), "open")
    entry_price_2 = calculate_backtest_prices(price_2, direction_2, float(runtime_config["slippage_bps"]), "open")

    return {
        "opened_at": timestamp.isoformat(),
        "opened_index": int(bar_index),
        "ticker_1": ticker_1,
        "ticker_2": ticker_2,
        "direction_1": direction_1,
        "direction_2": direction_2,
        "entry_zscore": float(metrics["latest_zscore"]),
        "hedge_ratio": float(metrics["hedge_ratio"]),
        "intercept": float(metrics["intercept"]),
        "quantity_1": float(quantity_1),
        "quantity_2": float(quantity_2),
        "entry_price_1": float(entry_price_1),
        "entry_price_2": float(entry_price_2),
        "capital_base": capital_base,
        "fee_rate": float(runtime_config["fee_rate"]),
    }


def close_backtest_position(position, current_zscore, price_1, price_2, timestamp, runtime_config, exit_reason):
    exit_price_1 = calculate_backtest_prices(price_1, position["direction_1"], float(runtime_config["slippage_bps"]), "close")
    exit_price_2 = calculate_backtest_prices(price_2, position["direction_2"], float(runtime_config["slippage_bps"]), "close")

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

    return {
        "opened_at": position["opened_at"],
        "closed_at": timestamp.isoformat(),
        "ticker_1": position["ticker_1"],
        "ticker_2": position["ticker_2"],
        "direction_1": position["direction_1"],
        "direction_2": position["direction_2"],
        "entry_zscore": position["entry_zscore"],
        "exit_zscore": float(current_zscore),
        "exit_reason": exit_reason,
        "hedge_ratio": position["hedge_ratio"],
        "intercept": position["intercept"],
        "quantity_1": position["quantity_1"],
        "quantity_2": position["quantity_2"],
        "entry_price_1": position["entry_price_1"],
        "entry_price_2": position["entry_price_2"],
        "exit_price_1": float(exit_price_1),
        "exit_price_2": float(exit_price_2),
        "gross_pnl": float(gross_pnl),
        "fees_paid": float(fees_paid),
        "net_pnl": float(net_pnl),
        "return_pct": float(return_pct),
    }


def backtest_pair(pair_row, runtime_config):
    frame_1 = get_kline_frame(pair_row["sym_1"])
    frame_2 = get_kline_frame(pair_row["sym_2"])
    if frame_1.empty or frame_2.empty:
        return []

    merged = frame_1.merge(frame_2, on="timestamp", suffixes=("_1", "_2"))
    lookback_bars = max(int(runtime_config["backtest_lookback_bars"]), z_score_window + 5)
    if len(merged) <= lookback_bars:
        return []

    trades = []
    active_position = None
    max_holding_bars = int(runtime_config["max_holding_bars"])

    for index in range(lookback_bars, len(merged)):
        history = merged.iloc[index - lookback_bars:index + 1]
        series_1 = history["close_1"].tolist()
        series_2 = history["close_2"].tolist()
        metrics = calculate_pair_metrics(series_1, series_2, z_score_window)
        timestamp = history.iloc[-1]["timestamp"].to_pydatetime()
        current_price_1 = float(history.iloc[-1]["close_1"])
        current_price_2 = float(history.iloc[-1]["close_2"])

        if (
            metrics["latest_zscore"] is None
            or metrics["coint_flag"] != 1
            or not (min_half_life <= metrics["half_life"] <= max_half_life)
        ):
            if active_position is not None:
                trades.append(
                    close_backtest_position(
                        active_position,
                        0.0,
                        current_price_1,
                        current_price_2,
                        timestamp,
                        runtime_config,
                        "model_breakdown",
                    )
                )
                active_position = None
            continue

        if active_position is None:
            if abs(metrics["latest_zscore"]) < float(runtime_config["entry_zscore"]):
                continue

            active_position = build_backtest_position(
                metrics,
                pair_row["sym_1"],
                pair_row["sym_2"],
                current_price_1,
                current_price_2,
                timestamp,
                index,
                runtime_config,
            )
            continue

        exit_reason = None
        current_abs_zscore = abs(metrics["latest_zscore"])
        if current_abs_zscore <= float(runtime_config["exit_zscore"]):
            exit_reason = "mean_reversion"
        elif current_abs_zscore >= float(runtime_config["stop_zscore"]):
            exit_reason = "zscore_stop"
        elif (index - active_position["opened_index"]) >= max_holding_bars:
            exit_reason = "time_stop"

        if not exit_reason:
            continue

        trades.append(
            close_backtest_position(
                active_position,
                metrics["latest_zscore"],
                current_price_1,
                current_price_2,
                timestamp,
                runtime_config,
                exit_reason,
            )
        )
        active_position = None

    if active_position is not None:
        last_row = merged.iloc[-1]
        trades.append(
            close_backtest_position(
                active_position,
                0.0,
                float(last_row["close_1"]),
                float(last_row["close_2"]),
                last_row["timestamp"].to_pydatetime(),
                runtime_config,
                "end_of_test",
            )
        )

    return trades


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
        return

    with BACKTEST_TRADES_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(trades[0].keys()))
        writer.writeheader()
        writer.writerows(trades)


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

    all_trades = []
    for _, pair_row in ranked_pairs.head(min(top_pairs_to_scan, int(runtime_config["backtest_top_pairs"]))).iterrows():
        all_trades.extend(backtest_pair(pair_row.to_dict(), runtime_config))

    write_backtest_results(all_trades)

    total_net_pnl = sum(trade["net_pnl"] for trade in all_trades)
    win_rate = (
        sum(1 for trade in all_trades if trade["net_pnl"] > 0) / len(all_trades) * 100
        if all_trades
        else 0
    )
    summary = {
        "total_trades": len(all_trades),
        "total_net_pnl": total_net_pnl,
        "win_rate": win_rate,
        "generated_at": datetime.utcnow().isoformat(),
    }
    print(json.dumps(summary, indent=4))


if __name__ == "__main__":
    main()
