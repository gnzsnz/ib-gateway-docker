# mvc_core/plotting/figures.py
from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mvc_core.performances.metrics_services import (
    DEFAULT_PERIODS_PER_YEAR,
    DEFAULT_RISK_FREE,
    cagr,
    max_drawdown,
    sharpe_ratio,
    total_return_pct,
)

from .markers import add_decision_markers

COLORS = {
    "price":   "#1f8799",
    "equity":  "#b90202",
    "Buy&Hold":"#160066",
    "indicator": "#909090",
    "spike":   "#4d4d4d",
}

def _slice_series(s, start=None, end=None) -> pd.Series:
    if s is None: return pd.Series(dtype=float)
    out = s if isinstance(s, pd.Series) else pd.Series(s)
    out = out.dropna()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    if start is not None: out = out.loc[start:]
    if end is not None:   out = out.loc[:end]
    return out.astype(float)

def _align_to_index(s: Optional[pd.Series], idx: pd.DatetimeIndex) -> pd.Series:
    if s is None:
        return pd.Series(dtype=float)
    out = pd.Series(s, dtype=float).dropna()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.reindex(idx).dropna()


def _pick_equity_series(equity, start=None, end=None) -> pd.Series:
    if equity is None: return pd.Series(dtype=float)
    if isinstance(equity, pd.Series):
        return _slice_series(equity, start, end)
    df = equity.copy(); df.index = pd.to_datetime(df.index).tz_localize(None)
    col = "TotalValue" if "TotalValue" in df.columns else df.columns[0]
    return _slice_series(df[col], start, end)

def _metrics_text(eq: pd.Series, rf: float, periods_per_year: int) -> str:
    if eq is None or eq.empty:
        return "<b>Metrics</b><br>n/a"
    tot = total_return_pct(eq)
    shp = sharpe_ratio(eq, rf=rf, periods_per_year=periods_per_year)
    mdd = max_drawdown(eq) * 100.0
    cg  = cagr(eq)
    cg_txt = "n/a" if (pd.isna(cg)) else f"{cg:.2%}"
    return (
        "<b>Metrics</b><br>"
        f"Total Profit: {tot:.2f}%<br>"
        f"Sharpe (rfr={rf:.0%}): {shp:.2f}<br>"
        f"MDD: {mdd:.2f}%<br>"
        f"CAGR: {cg_txt}"
    )

def _apply_layout(fig: go.Figure, title: str) -> None:
    fig.update_layout(
        title=title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        margin=dict(l=60, r=40, t=60, b=40),
        height=820,
    )
    fig.update_xaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikedash="dot", spikethickness=1, spikecolor=COLORS["spike"],
    )


def plot_price_only(
    price: pd.Series,
    instrument: Optional[str] = None,
    start=None,
    end=None,
    title: str = "",
    decisions=None,
) -> go.Figure:
    """
    Plot uniquement la courbe de prix avec les markers de décisions.
    Pas d'indicateur, pas de suivi PnL.
    """
    px = _slice_series(price, start, end)

    fig = make_subplots(
        rows=1, cols=1,
        subplot_titles=(f"Futures Price {instrument or ''}",),
    )

    fig.add_trace(
        go.Scatter(
            x=px.index,
            y=px.values,
            mode="lines",
            name="Close",
            line=dict(color=COLORS["price"], width=2),
            hovertemplate="Close : %{y:.2f}<extra></extra>",
        ),
        row=1, col=1
    )

    if decisions is not None:
        add_decision_markers(fig, decisions, row=1, col=1)

    fig.update_layout(
        title=title or f"Futures Price {instrument or ''}",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        margin=dict(l=60, r=40, t=60, b=40),
        height=500,
    )
    fig.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikethickness=1,
        spikecolor=COLORS["spike"],
    )

    return fig


# --- add below COLORS and helpers in figures.py ---

from collections import OrderedDict
from typing import Mapping, Union

IndicatorInput = Union[pd.Series, Mapping[str, pd.Series], None]
ThresholdInput = Union[
    float, Tuple[float, float], pd.Series,
    Mapping[str, Union[float, Tuple[float, float]]],
    None
]

def _norm_multi_indicators(
    indicator: IndicatorInput, start=None, end=None
) -> "OrderedDict[str, pd.Series]":
    """
    Accepts:
      - None
      - pd.Series  -> {"Indicator": series}
      - dict[str, Series] -> as-is
    Applies slicing & tz-normalization like _slice_series().
    """
    out: "OrderedDict[str, pd.Series]" = OrderedDict()
    if indicator is None:
        return out
    if isinstance(indicator, pd.Series):
        out["Indicator"] = _slice_series(indicator, start, end)
        return out
    if isinstance(indicator, Mapping):
        for name, ser in indicator.items():
            out[str(name)] = _slice_series(ser, start, end)
        return out
    raise TypeError("indicator must be a pd.Series or a dict[str, pd.Series]")

def _align_multi_to_index(
    inds: "OrderedDict[str, pd.Series]", idx: pd.DatetimeIndex
) -> "OrderedDict[str, pd.Series]":
    aligned: "OrderedDict[str, pd.Series]" = OrderedDict()
    for name, ser in inds.items():
        aligned[name] = _align_to_index(ser, idx)
    return aligned



def plot_price_equity_indicator(
    price: pd.Series,
    equity,                                 
    instrument: Optional[str] = None,
    indicator: IndicatorInput = None,        
    indicator_name: Optional[str] = None,    
    thresholds: ThresholdInput = None,       
    start=None, end=None,
    title: str = "",
    decisions=None,                           
    risk_free_rate: float = DEFAULT_RISK_FREE,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> go.Figure:
    px = _slice_series(price, start, end)
    eq = _pick_equity_series(equity, start, end)

    # Normalize indicators input (single or multiple)
    inds = _norm_multi_indicators(indicator, start, end)

    # If we have equity, align everything to equity index
    if eq is not None and not eq.empty:
        eq_idx = eq.index
        px     = _align_to_index(px, eq_idx)
        inds   = _align_multi_to_index(inds, eq_idx)
    else:
        px = _slice_series(price, start, end)
        # inds already sliced above

    if len(inds) >= 1:
        ind_idx = next(iter(inds.values())).index
    else:
        ind_idx = px.index  

    # Subplot titles
    if len(inds) <= 1:
        ind_title = indicator_name or (next(iter(inds.keys())) if inds else "Indicator")
        ind_title = "Model Visualization"
    else:
        ind_title = "Indicators"

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.45, 0.25, 0.30],
        vertical_spacing=0.06,
        subplot_titles=(f"Futures Price {instrument}", ind_title, "Equity vs Buy&Hold"),
    )

    # Panel 1: price + markers + metrics
    fig.add_trace(
        go.Scatter(x=px.index, y=px.values, mode="lines", name="Close",
                   line=dict(color=COLORS["price"], width=2),
                   hovertemplate="Close : %{y:.2f}<extra></extra>"),
        row=1, col=1
    )
    if decisions is not None:
        add_decision_markers(fig, decisions, row=1, col=1)

    # Panel 2: indicator(s)
    if len(inds) == 1:
        # single line behaviour preserved
        name, ser = next(iter(inds.items()))
        # name = "Score Visualization"
        if not ser.empty:
            fig.add_trace(
                go.Scatter(x=ser.index, y=ser.values, mode="lines", name=name,
                           line=dict(color=COLORS["indicator"], width=1.5),
                           hovertemplate=f"{name} : "+"%{y:.2f}<extra></extra>"),
                row=2, col=1
            )
    elif len(inds) > 1:
        # multiple indicators: give distinct styles
        # convention: if we find "LONG"/"SHORT" in names, style accordingly
        for name, ser in inds.items():
            if ser.empty:
                continue
            style = dict(width=1.5)
            if "SHORT" in name.upper():
                style.update(dict(dash="dot"))
            fig.add_trace(
                go.Scatter(x=ser.index, y=ser.values, mode="lines", name=name,
                           line=style, hovertemplate=f"{name} : "+"%{y:.2f}<extra></extra>"),
                row=2, col=1
            )

    # thresholds (single float/tuple or per-indicator dict)
    def _add_threshold(val, label=None):
        # 1) pd.Series
        if isinstance(val, pd.Series):
            s = _align_to_index(val, ind_idx) if ind_idx is not None else _slice_series(val, start, end)
            if s is not None and not s.empty:
                fig.add_trace(
                    go.Scatter(
                        x=s.index, y=s.values, mode="lines",
                        name=label or "Threshold",
                        line=dict(width=1, dash="dot"),
                        hovertemplate=(f"{label or 'Threshold'} : " + "%{y:.2f}<extra></extra>")
                    ),
                    row=2, col=1
                )
            return

        # 2) Tuple (low, high) 
        if isinstance(val, tuple) and len(val) == 2:
            low, high = val
            fig.add_hline(y=float(low),  line=dict(width=1, dash="dot"), row=2, col=1)
            fig.add_hline(y=float(high), line=dict(width=1, dash="dot"), row=2, col=1)
            return

        # 3) float
        if isinstance(val, (int, float)):
            fig.add_hline(y=float(val), line=dict(width=1, dash="dot"), row=2, col=1)
            return

    if thresholds is not None:
        if isinstance(thresholds, Mapping):
            # format dict: peut contenir scalaires/tuples OU séries
            # cas fréquent: {"up": Series|float, "down": Series|float}
            # sinon: on parcourt tous les items
            if "up" in thresholds or "down" in thresholds:
                if thresholds.get("up") is not None:
                    _add_threshold(thresholds["up"], label="TH_up")
                if thresholds.get("down") is not None:
                    _add_threshold(thresholds["down"], label="TH_down")
            else:
                for k, v in thresholds.items():
                    _add_threshold(v, label=str(k))
        else:
            # scalaire ou tuple: appliqué globalement
            _add_threshold(thresholds)

    # Panel 3: equity vs buy&hold (and other series if present)
    if eq is not None and not eq.empty:
        fig.add_trace(
            go.Scatter(x=eq.index, y=eq.values, mode="lines", name="Equity",
                       line=dict(color=COLORS["equity"], width=2),
                       hovertemplate="Equity : %{y:.2f}<extra></extra>"),
            row=3, col=1
        )
        if isinstance(equity, pd.DataFrame):
            # Colonnes déjà tracées (éviter les doublons)
            main_col = "TotalValue" if "TotalValue" in equity.columns else equity.columns[0]
            plotted_cols = {main_col}
            
            # D'abord tracer Buy&Hold si présent
            bh_candidates = ("Buy&Hold", "BuyAndHold", "Buy_and_Hold", "Buy_and_Hold_Value")
            for bh_col in bh_candidates:
                if bh_col in equity.columns:
                    bh = _slice_series(equity[bh_col], start, end)
                    fig.add_trace(
                        go.Scatter(x=bh.index, y=bh.values, mode="lines", name="Buy&Hold",
                                   line=dict(color=COLORS["Buy&Hold"])),
                        row=3, col=1
                    )
                    plotted_cols.add(bh_col)
                    break
            
            # Tracer toutes les autres colonnes (stratégies de base, etc.)
            extra_colors = ["#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
            color_idx = 0
            for col in equity.columns:
                if col not in plotted_cols:
                    ser = _slice_series(equity[col], start, end)
                    if not ser.empty:
                        color = extra_colors[color_idx % len(extra_colors)]
                        fig.add_trace(
                            go.Scatter(x=ser.index, y=ser.values, mode="lines", name=col,
                                       line=dict(color=color, width=1.5),
                                       hovertemplate=f"{col} : "+"%{y:.2f}<extra></extra>"),
                            row=3, col=1
                        )
                        color_idx += 1

    final_title = title or (f"{instrument} — Price/Indicator/Equity" if instrument else "Price/Indicator/Equity")
    _apply_layout(fig, final_title)
    return fig


def plot_price_equity(
    price: pd.Series,
    equity,                                 
    instrument: Optional[str] = None,
    start=None, end=None,
    title: str = "",
    decisions=None,                           
    risk_free_rate: float = DEFAULT_RISK_FREE,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    equity_name: str = "Equity",
) -> go.Figure:
    """
    Plot price and equity without the indicator panel.
    Same as plot_price_equity_indicator but with only 2 panels.
    equity_name: legend name of the main equity line.
    """
    px = _slice_series(price, start, end)
    eq = _pick_equity_series(equity, start, end)

    # If we have equity, align price to equity index
    if eq is not None and not eq.empty:
        eq_idx = eq.index
        px = _align_to_index(px, eq_idx)
    else:
        px = _slice_series(price, start, end)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.50, 0.50],
        vertical_spacing=0.06,
        subplot_titles=(f"Futures Price {instrument}", "Equity vs Buy&Hold"),
    )

    # Panel 1: price + markers + metrics
    fig.add_trace(
        go.Scatter(x=px.index, y=px.values, mode="lines", name="Close",
                   line=dict(color=COLORS["price"], width=2),
                   hovertemplate="Close : %{y:.2f}<extra></extra>"),
        row=1, col=1
    )
    if decisions is not None:
        add_decision_markers(fig, decisions, row=1, col=1)

    # Panel 2: equity vs buy&hold (and other series if present)
    if eq is not None and not eq.empty:
        fig.add_trace(
            go.Scatter(x=eq.index, y=eq.values, mode="lines", name=equity_name,
                       line=dict(color=COLORS["equity"], width=2),
                       hovertemplate=f"{equity_name} : "+"%{y:.2f}<extra></extra>"),
            row=2, col=1
        )
        if isinstance(equity, pd.DataFrame):
            # Colonnes déjà tracées (éviter les doublons)
            main_col = "TotalValue" if "TotalValue" in equity.columns else equity.columns[0]
            plotted_cols = {main_col}
            
            # D'abord tracer Buy&Hold si présent
            bh_candidates = ("Buy&Hold", "BuyAndHold", "Buy_and_Hold", "Buy_and_Hold_Value")
            for bh_col in bh_candidates:
                if bh_col in equity.columns:
                    bh = _slice_series(equity[bh_col], start, end)
                    fig.add_trace(
                        go.Scatter(x=bh.index, y=bh.values, mode="lines", name="Buy&Hold",
                                   line=dict(color=COLORS["Buy&Hold"])),
                        row=2, col=1
                    )
                    plotted_cols.add(bh_col)
                    break
            
            # Tracer toutes les autres colonnes (stratégies de base, etc.)
            extra_colors = ["#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
            color_idx = 0
            for col in equity.columns:
                if col not in plotted_cols:
                    ser = _slice_series(equity[col], start, end)
                    if not ser.empty:
                        color = extra_colors[color_idx % len(extra_colors)]
                        fig.add_trace(
                            go.Scatter(x=ser.index, y=ser.values, mode="lines", name=col,
                                       line=dict(color=color, width=1.5),
                                       hovertemplate=f"{col} : "+"%{y:.2f}<extra></extra>"),
                            row=2, col=1
                        )
                        color_idx += 1

    final_title = title or (f"{instrument} — Price/Equity" if instrument else "Price/Equity")
    _apply_layout(fig, final_title)
    return fig
