"""
Fusion strategy (sugar SB11): majority vote of six strategies, run with
backtest_engine.py.

backtest_engine.py and strategies/ come unchanged from Benoit Decomps' repository
(ben-245dev/strategies_benoit_decomps, commit ea23962), except that
strat_2_fixed.py no longer writes zscore.csv and, at Benoit's request, the
RSI, reversal and momentum strategies compute on the Open instead of the
Close. FUSION_STRATEGIES and the
run_backtest arguments below are those of its run.py, without the portfolio
stop (removed at Benoit's request). Keep these files as close
as possible to that repository so its updates can be diffed and copied over.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from mvc_core.adapters.data.db_loading.postgres_futures_loader import load_futures
from mvc_core.adapters.data.db_loading.postgres_sugar_spot_loader import (
    format_sugar_spot,
    load_sugar_spot_raw,
)

from .backtest_engine import run_backtest

STRATEGIES_DIR = Path(__file__).resolve().parent / "strategies"

# (strategy file, weight). The 1.01 weight breaks the ties of the six-way vote.
FUSION_STRATEGIES = [
    ("strat_2_fixed.py", 1),
    ("strat_3_fixed.py", 1),
    ("strategy_zscore20.py", 1),
    ("strategy_rsi14.py", 1.01),
    ("strategy_mom_20_50.py", 1),
    ("strategy_reversal.py", 1),
]

FUSION_BACKTEST_ARGS = dict(
    date_mode="intersection",
    combine_mode="majority",
    min_hold_days=3,
    min_hold_unit="trading",
    equity_mode="fixed_notional",
    execution="close",
)

# SB11 daily prices sent by Benoit (date, close, open, high, low, volume in
# c/lb), kept exactly as he sent them: his series rolls to the next contract
# about two weeks before expiry, ours (IBKR / DB) only at expiry. They cover
# 2014-01-02 to 2026-10-23; later dates come from the DB futures.
BENOIT_SB11_FILE = Path(__file__).resolve().parent / "data" / "dataset_sb11_benoit.csv"


def load_sb11_prices() -> pd.DataFrame:
    """
    SB11 Open / Close per date: Benoit's file, then the DB futures for the
    dates after its last one.
    """
    benoit = pd.read_csv(BENOIT_SB11_FILE, parse_dates=["date"]).set_index("date")
    benoit = benoit.rename(columns={"open": "Open", "close": "Close"})[["Open", "Close"]]

    db = load_futures(asset_name="SB11")[["Open", "Close"]]
    db.index = pd.DatetimeIndex(db.index).tz_localize(None).normalize()
    db = db[~db.index.duplicated(keep="last")]
    db = db[db.index > benoit.index.max()]

    return pd.concat([benoit, db]).dropna(subset=["Open", "Close"])


def load_spot_mid(asset_name: str) -> pd.Series:
    """
    Spot mid (VHP / THP) on its own quote dates, as in Benoit's preprocessing:
    BID and OFFER are each forward-filled, then MID = (BID + OFFER) / 2.
    """
    spot = format_sugar_spot(load_sugar_spot_raw(asset_name=asset_name), keep_bid_offer=True)
    spot.index = pd.DatetimeIndex(spot.index).tz_localize(None).normalize()
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    bid, offer = spot["BID"].ffill(), spot["OFFER"].ffill()
    return (bid + offer) / 2


def load_fusion_input() -> pd.DataFrame:
    """
    The engine's input, built exactly as Benoit's preprocessing: SB11 Open /
    Close (load_sb11_prices) and the VHP / THP spot mids side by side on the
    union of their dates, every column forward-filled, then the rows without
    Close, MID_VHP or MID_THP dropped. A spot-only date therefore carries the
    previous SB11 prices. The RSI, reversal and momentum strategies compute
    their signal on the Open, known during the day, and orders execute at the
    Close of that same day (execution="close").
    """
    df = pd.concat(
        [
            load_sb11_prices(),
            load_spot_mid("VHP").rename("MID_VHP"),
            load_spot_mid("THP").rename("MID_THP"),
        ],
        axis=1,
    ).sort_index()
    df = df.ffill().dropna(subset=["Close", "MID_THP", "MID_VHP"])
    df = df.rename_axis("Date").reset_index()
    return df[["Date", "Open", "Close", "MID_VHP", "MID_THP"]]


def run_fusion(notional: float) -> Dict[str, Any]:
    """run_backtest result of the Fusion strategy, PnL in fixed `notional`."""
    specs = [(str(STRATEGIES_DIR / file), weight) for file, weight in FUSION_STRATEGIES]
    return run_backtest(load_fusion_input(), specs, notional=notional, **FUSION_BACKTEST_ARGS)
