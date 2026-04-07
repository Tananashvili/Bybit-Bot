from pathlib import Path
import json
import os

from dotenv import load_dotenv
from pybit.unified_trading import HTTP

from Strategy.config_strategy_api import (
    entry_zscore as default_entry_zscore,
    exit_zscore as default_exit_zscore,
    kline_limit,
    mode,
    stop_zscore as default_stop_zscore,
    testnet,
    timeframe,
    train_window,
    z_score_window,
)

load_dotenv()

api_key_mainnet = os.getenv("api_key_mainnet")
api_secret_mainnet = os.getenv("api_secret_mainnet")
api_key_testnet = os.getenv("api_key_testnet")
api_secret_testnet = os.getenv("api_secret_testnet")

api_key = api_key_testnet if testnet else api_key_mainnet
api_secret = api_secret_testnet if testnet else api_secret_mainnet

limit_order_basis = True

CONFIG_PATH = Path("config.json")
PAPER_STATE_PATH = Path("paper_state.json")
PAPER_TRADES_PATH = Path("paper_trades.csv")
BACKTEST_TRADES_PATH = Path("backtest_trades.csv")

DEFAULT_CONFIG = {
    "entry_zscore": default_entry_zscore,
    "exit_zscore": default_exit_zscore,
    "stop_zscore": default_stop_zscore,
    "paper_balance": 250.0,
    "max_open_positions": 3,
    "cash_reserve_pct": 0.01,
    "leverage": 3.0,
    "open_fee_rate": 0.0002,
    "close_fee_rate": 0.00055,
    "open_slippage_bps": 0.0,
    "close_slippage_bps": 2.0,
    "profit_lock_activation_pct": 5.0,
    "profit_lock_min_return_pct": 0.5,
    "profit_lock_keep_ratio": 0.5,
    "max_holding_bars": 72,
    "pair_refresh_hours": 4,
    "portfolio_update_interval_minutes": 60,
    "loop_sleep_seconds": 60,
    "backtest_top_pairs": 10,
    "backtest_lookback_bars": train_window,
}


def build_default_paper_state(runtime_config):
    return {
        "cash_balance": float(runtime_config["paper_balance"]),
        "active_positions": [],
        "last_portfolio_update_sent_at": None,
        "paper_balance_base": float(runtime_config["paper_balance"]),
    }


session_public = HTTP(testnet=testnet)
session_private = (
    HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret,
    )
    if api_key and api_secret
    else HTTP(testnet=testnet)
)


def load_runtime_config():
    if not CONFIG_PATH.exists():
        save_runtime_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = json.load(file)

    merged = DEFAULT_CONFIG.copy()
    merged.update(loaded)
    return merged


def save_runtime_config(config):
    CONFIG_PATH.write_text(
        json.dumps(config, indent=4),
        encoding="utf-8",
    )


def load_paper_state():
    runtime_config = load_runtime_config()
    default_state = build_default_paper_state(runtime_config)

    if not PAPER_STATE_PATH.exists():
        return default_state

    with PAPER_STATE_PATH.open("r", encoding="utf-8") as file:
        state = json.load(file)
    if not state:
        return default_state

    state.setdefault("active_positions", [])
    state.setdefault("last_portfolio_update_sent_at", None)
    state.setdefault("paper_balance_base", float(runtime_config["paper_balance"]))
    state.setdefault("cash_balance", float(state["paper_balance_base"]))

    # If the wallet config changed and there are no open trades, start a fresh paper wallet.
    if (
        not state["active_positions"]
        and float(state["paper_balance_base"]) != float(runtime_config["paper_balance"])
    ):
        return default_state

    return state


def save_paper_state(state):
    runtime_config = load_runtime_config()
    state.setdefault("paper_balance_base", float(runtime_config["paper_balance"]))
    PAPER_STATE_PATH.write_text(
        json.dumps(state, indent=4),
        encoding="utf-8",
    )


def clear_paper_state():
    if PAPER_STATE_PATH.exists():
        PAPER_STATE_PATH.unlink()


def get_position_variables():
    state = load_paper_state()
    return state or {}
