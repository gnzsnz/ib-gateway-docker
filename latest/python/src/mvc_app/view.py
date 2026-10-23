from __future__ import annotations

from typing import Any, Dict, Optional

from matplotlib.figure import Figure
import pandas as pd

from mvc_core.optimize.oos_reconstruction_services import crop_oos_output
from mvc_core.plotting.figures import plot_price_equity, plot_price_equity_indicator, plot_price_only


def build_wf_oos_figure_from_oos(
    *,
    oos: Dict[str, Any],
    instrument: str,
    title_suffix: str = "",
    start_date : Optional[str] = None,
    end_date : Optional[str] = None,
) -> Figure:

    if start_date is None:
        start_date = oos["equity_oos_df"].index[0]
    if end_date is None:
        end_date = oos["equity_oos_df"].index[-1]


    display_initial_value = (
        float(oos.get("display_initial_value"))
        if oos.get("display_initial_value") is not None
        else float(oos.get("initial_inv") or 0.0) or None
    )
    oos = crop_oos_output(
        oos,
        start_date=start_date,
        end_date=end_date,
        initial_value=None,
        display_initial_value=display_initial_value,
    )

    price = oos["price"]
    equity_df: pd.DataFrame = oos["equity_oos_df"]
    decisions = oos.get("decisions")
    indicator = oos.get("indicator")
    thresholds = oos.get("thresholds")

    title = f"OOS — {instrument}"
    if title_suffix:
        title += f" ({title_suffix})"

    fig = plot_price_equity_indicator(
        price=price,
        equity=equity_df,
        instrument=instrument,
        indicator=({"Source": indicator} if indicator is not None else None),
        thresholds=thresholds,
        decisions=decisions,
        title=title,
    )
    return fig


def build_wf_oos_figure_from_oos_no_indicator(
    *,
    oos: Dict[str, Any],
    instrument: str,
    title_suffix: str = "",
    start_date : Optional[str] = None,
    end_date : Optional[str] = None,
) -> Figure:
    """
    Same as build_wf_oos_figure_from_oos but without the indicator panel.
    """
    if start_date is None:
        start_date = oos["equity_oos_df"].index[0]
    if end_date is None:
        end_date = oos["equity_oos_df"].index[-1]

    display_initial_value = (
        float(oos.get("display_initial_value"))
        if oos.get("display_initial_value") is not None
        else float(oos.get("initial_inv") or 0.0) or None
    )
    oos = crop_oos_output(
        oos,
        start_date=start_date,
        end_date=end_date,
        initial_value=None,
        display_initial_value=display_initial_value,
    )

    price = oos["price"]
    equity_df: pd.DataFrame = oos["equity_oos_df"]
    decisions = oos.get("decisions")

    title = f"OOS — {instrument}"
    if title_suffix:
        title += f" ({title_suffix})"

    fig = plot_price_equity(
        price=price,
        equity=equity_df,
        instrument=instrument,
        decisions=decisions,
        title=title,
    )
    return fig


def build_wf_oos_figure_price_only(
    *,
    oos: Dict[str, Any],
    instrument: str,
    title_suffix: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Figure:
    """
    Plot uniquement la courbe de prix avec les markers de décisions.
    Pas d'indicateur, pas de suivi PnL.
    """
    if start_date is None:
        start_date = oos["equity_oos_df"].index[0]
    if end_date is None:
        end_date = oos["equity_oos_df"].index[-1]

    display_initial_value = (
        float(oos.get("display_initial_value"))
        if oos.get("display_initial_value") is not None
        else float(oos.get("initial_inv") or 0.0) or None
    )
    oos = crop_oos_output(
        oos,
        start_date=start_date,
        end_date=end_date,
        initial_value=None,
        display_initial_value=display_initial_value,
    )

    price = oos["price"]
    decisions = oos.get("decisions")

    title = f"OOS — {instrument}"
    if title_suffix:
        title += f" ({title_suffix})"

    fig = plot_price_only(
        price=price,
        instrument=instrument,
        decisions=decisions,
        title=title,
    )
    return fig


def export_profile_trades_csv(profile_name: str, output_path: str) -> None:
    """
    Récupère les trades d'un profil et les exporte en CSV.

    Colonnes : date (yyyy-mm-dd), trade (+1 = LONG, -1 = SHORT).

    Args:
        profile_name: Nom du profil (ex: "wf_sb11").
        output_path: Chemin de sortie (ex: "/tmp/trades_wf_sb11.csv").
    """
    from pathlib import Path

    from mvc_app.jobs import JobConfig, get_backtest_view
    from mvc_core.performances.trades_reconstruction import build_trades_dataframe, print_trades_summary

    job_cfg = JobConfig(profile_name=profile_name)
    res = get_backtest_view(job_cfg)

    decisions = res["oos"].get("decisions", [])
    if not decisions:
        print(f"No decisions found for profile '{profile_name}'.")
        return

    trades_df = build_trades_dataframe(decisions, include_open_positions=True)
    print_trades_summary(trades_df)

    signals = trades_df[["entry_date", "side"]].copy()
    signals["trade"] = signals["side"].map({"LONG": 1, "SHORT": -1})
    signals = signals.rename(columns={"entry_date": "date"})
    signals["date"] = pd.to_datetime(signals["date"]).dt.strftime("%Y-%m-%d")
    signals = signals[["date", "trade"]].sort_values("date").reset_index(drop=True)

    signals.to_csv(output_path, index=False)
    print(f"Trades saved to {Path(output_path).resolve()}")


# Fusion: majority vote of six sugar strategies (see mvc_app/fusion). Its PnL is
# shown like the other sugar strategies': one FUSION_POSITION_NOTIONAL position
# on a FUSION_INITIAL_INV capital.
FUSION_INSTRUMENT = "SB11"
FUSION_INITIAL_INV = 200_000_000
FUSION_POSITION_NOTIONAL = 200_000_000


def _run_fusion(start_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Prix, equity (Fusion, Buy&Hold) et entrées de la stratégie Fusion,
    recadrés à partir de start_date (equity rebasée sur l'investissement initial).
    """
    from mvc_app.fusion.fusion_services import run_fusion

    result = run_fusion(notional=FUSION_POSITION_NOTIONAL)
    bt = result["data"].set_index("Date")
    trades = result["combined_trades"]
    open_trades = pd.DataFrame(result["combined_open_positions"], columns=trades.columns)
    entries = pd.concat([trades, open_trades], ignore_index=True)[["entry_date", "direction", "entry_price"]]

    if start_date is not None:
        bt = bt.loc[start_date:]
        entries = entries[entries["entry_date"] >= pd.Timestamp(start_date)]

    price = bt["Close"]
    pnl = bt["Equity_Fixed_Notional"] - bt["Equity_Fixed_Notional"].iloc[0]
    equity = pd.DataFrame({
        "Fusion": FUSION_INITIAL_INV + pnl,
        "Buy&Hold": FUSION_INITIAL_INV + FUSION_POSITION_NOTIONAL * (price / price.iloc[0] - 1),
    })
    decisions = pd.DataFrame({
        "date": entries["entry_date"],
        "action": entries["direction"].map({"Long": "OPEN_LONG", "Short": "OPEN_SHORT"}),
        "price": entries["entry_price"],
    }).sort_values("date").reset_index(drop=True)
    return {"price": price, "equity": equity, "decisions": decisions}


def build_fusion_figure(start_date: Optional[str] = None):
    """
    Graphique prix + equity de la stratégie Fusion, recadré à partir de
    start_date (equity rebasée sur l'investissement initial).
    """
    fusion = _run_fusion(start_date=start_date)
    return plot_price_equity(
        price=fusion["price"],
        equity=fusion["equity"],
        instrument=FUSION_INSTRUMENT,
        decisions=fusion["decisions"],
        title="Fusion Strategy",
        equity_name="Fusion",
    )


def build_fusion_client_figure(start_date: Optional[str] = None):
    """
    Version client du graphique Fusion : prix et entrées uniquement, sans
    suivi PnL (comme build_wf_oos_figure_price_only).
    """
    fusion = _run_fusion(start_date=start_date)
    return plot_price_only(
        price=fusion["price"],
        instrument=FUSION_INSTRUMENT,
        decisions=fusion["decisions"],
        title="Fusion Strategy",
    )


def export_fusion_trades_csv(output_path: str) -> None:
    """
    Exporte les trades de la stratégie Fusion en CSV, au même format
    que export_profile_trades_csv : date (yyyy-mm-dd), trade (+1 = LONG, -1 = SHORT).
    """
    from pathlib import Path

    decisions = _run_fusion()["decisions"]
    if decisions.empty:
        print("No decisions found for the Fusion strategy.")
        return

    signals = pd.DataFrame({
        "date": pd.to_datetime(decisions["date"]).dt.strftime("%Y-%m-%d"),
        "trade": decisions["action"].map({"OPEN_LONG": 1, "OPEN_SHORT": -1}),
    })
    print(f"Fusion: {len(signals)} trades, last {signals.iloc[-1].tolist()}")

    signals.to_csv(output_path, index=False)
    print(f"Trades saved to {Path(output_path).resolve()}")
