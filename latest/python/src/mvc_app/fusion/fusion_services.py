"""
Fusion strategy (sugar SB11): majority vote of six strategies, run with
backtest_engine.py.

backtest_engine.py and strategies/ come unchanged from Benoit Decomps' repository
(ben-245dev/strategies_benoit_decomps, commit ea23962), except that
strat_2_fixed.py no longer writes zscore.csv. FUSION_STRATEGIES and the
run_backtest arguments below are those of its run.py, without the portfolio
stop (removed at Benoit's request). Keep these files as close
as possible to that repository so its updates can be diffed and copied over.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from mvc_app.helpers.data_builder.data_sb11 import data_sb11_builder
from mvc_app.helpers.data_loader.data_loader_data import DataSource

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

# The seasonal strategies need two years of history before their 2018-01-01
# eval_start_date: load from the start of the SB11 history, like the other
# sugar profiles.
FUSION_START_LOAD = "2013-05-01"


def load_fusion_input() -> pd.DataFrame:
    """
    The engine's input: one row per SB11 date, with Close = SB11 close,
    MID_VHP / MID_THP = VHP / THP spot mids (forward-filled, as for the other
    sugar strategies). Orders execute at the close, so Open (required by the
    engine) is only a copy of Close.
    """
    today = datetime.today().strftime("%Y-%m-%d")
    clock, price_series = data_sb11_builder(
        FUSION_START_LOAD, "2027-01-01", FUSION_START_LOAD, today,
        "ffill", "dropna", source=DataSource.POSTGRES,
    )()

    df = pd.DataFrame({
        "Close": price_series["SB11"],
        "MID_VHP": price_series["VHP"],
        "MID_THP": price_series["THP"],
    }).reindex(clock.index)
    df.index = df.index.tz_localize(None).normalize()
    df = df.dropna(subset=["Close"]).rename_axis("Date").reset_index()
    df["Open"] = df["Close"]
    return df[["Date", "Open", "Close", "MID_VHP", "MID_THP"]]


def run_fusion(notional: float) -> Dict[str, Any]:
    """run_backtest result of the Fusion strategy, PnL in fixed `notional`."""
    specs = [(str(STRATEGIES_DIR / file), weight) for file, weight in FUSION_STRATEGIES]
    return run_backtest(load_fusion_input(), specs, notional=notional, **FUSION_BACKTEST_ARGS)
