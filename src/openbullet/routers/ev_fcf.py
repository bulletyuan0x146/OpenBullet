from __future__ import annotations

from copy import deepcopy
import json
from typing import Annotated, Literal

import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException, Query

from openbullet.providers.ev_fcf import EvFcfProvider
from openbullet.widgets.registry import register_widget

router = APIRouter(prefix="/equity", tags=["Equity"])
provider = EvFcfProvider()

MarketParam = Annotated[
    Literal["cn", "hk"],
    Query(description="Market code. Use 'cn' for A-shares or 'hk' for Hong Kong."),
]
SymbolParam = Annotated[
    str,
    Query(min_length=1, max_length=16, description="Ticker symbol, e.g. 600519 or 00700."),
]

MARKET_PARAM = {
    "paramName": "market",
    "value": "cn",
    "label": "Market",
    "type": "tabs",
    "description": "Select the market.",
    "options": [
        {"label": "A Share", "value": "cn"},
        {"label": "Hong Kong", "value": "hk"},
    ],
}
SYMBOL_PARAM = {
    "paramName": "symbol",
    "value": "600519",
    "label": "Symbol",
    "type": "text",
    "description": "Ticker symbol, e.g. 600519 or 00700.",
}
THEME_PARAM = {
    "paramName": "theme",
    "value": "dark",
    "label": "Theme",
    "type": "tabs",
    "description": "Chart theme.",
    "options": [
        {"label": "Dark", "value": "dark"},
        {"label": "Light", "value": "light"},
    ],
}


@register_widget(
    {
        "name": "EV / FCF",
        "description": "Annual enterprise value to free cash flow for A-share and Hong Kong stocks.",
        "category": "Valuation",
        "type": "table",
        "endpoint": "equity/ev_fcf",
        "gridData": {"w": 20, "h": 12},
        "source": ["AkShare"],
        "params": [deepcopy(MARKET_PARAM), deepcopy(SYMBOL_PARAM)],
        "data": {
            "table": {
                "showAll": True,
                "columnsDefs": [
                    {
                        "field": "fiscal_year",
                        "headerName": "Fiscal Year",
                        "cellDataType": "text",
                        "width": 120,
                    },
                    {
                        "field": "ev_to_fcf",
                        "headerName": "EV / FCF",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 120,
                    },
                    {
                        "field": "enterprise_value",
                        "headerName": "Enterprise Value",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 170,
                    },
                    {
                        "field": "free_cash_flow",
                        "headerName": "Free Cash Flow",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 160,
                    },
                    {
                        "field": "market_cap",
                        "headerName": "Market Cap",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 150,
                    },
                    {
                        "field": "cash",
                        "headerName": "Cash",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 140,
                    },
                    {
                        "field": "total_debt",
                        "headerName": "Total Debt",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 140,
                    },
                    {
                        "field": "currency",
                        "headerName": "Currency",
                        "cellDataType": "text",
                        "width": 110,
                    },
                    {
                        "field": "market_cap_method",
                        "headerName": "Market Cap Method",
                        "cellDataType": "text",
                        "width": 260,
                    },
                ],
            }
        },
    }
)
@router.get("/ev_fcf")
def get_ev_fcf(market: MarketParam = "cn", symbol: SymbolParam = "600519") -> list[dict]:
    try:
        return provider.get_ev_fcf(market=market, symbol=symbol)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch EV/FCF records for {market}:{symbol}: {exc}",
        ) from exc


@register_widget(
    {
        "name": "EV / FCF Chart",
        "description": "Annual EV/FCF trend for A-share and Hong Kong stocks.",
        "category": "Valuation",
        "type": "chart",
        "endpoint": "equity/ev_fcf/chart",
        "gridData": {"w": 24, "h": 12},
        "source": ["AkShare"],
        "params": [
            deepcopy(MARKET_PARAM),
            deepcopy(SYMBOL_PARAM),
            deepcopy(THEME_PARAM),
        ],
    }
)
@router.get("/ev_fcf/chart")
def get_ev_fcf_chart(
    market: MarketParam = "cn",
    symbol: SymbolParam = "600519",
    theme: Annotated[Literal["dark", "light"], Query(description="Chart theme.")] = "dark",
) -> dict:
    try:
        rows = provider.get_ev_fcf(market=market, symbol=symbol)
        return _build_ev_fcf_chart(rows=rows, market=market, symbol=symbol, theme=theme)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build EV/FCF chart for {market}:{symbol}: {exc}",
        ) from exc


def _build_ev_fcf_chart(
    *, rows: list[dict], market: str, symbol: str, theme: str
) -> dict:
    chart_rows = [
        row
        for row in rows
        if row.get("ev_to_fcf") is not None
        and row.get("free_cash_flow") is not None
        and row.get("free_cash_flow") > 0
    ]
    chart_rows = sorted(chart_rows, key=lambda row: row["fiscal_year"])
    colors = _theme_colors(theme)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[row["fiscal_year"] for row in chart_rows],
            y=[row["ev_to_fcf"] for row in chart_rows],
            name="EV / FCF",
            mode="lines+markers",
            line={"color": colors["line"], "width": 2},
            marker={"size": 8},
            customdata=[
                [
                    row.get("currency"),
                    row.get("enterprise_value"),
                    row.get("free_cash_flow"),
                    row.get("market_cap"),
                    row.get("cash"),
                    row.get("total_debt"),
                    row.get("market_cap_method"),
                ]
                for row in chart_rows
            ],
            hovertemplate=(
                "%{x}<br>"
                "EV / FCF: %{y:.2f}x<br>"
                "EV: %{customdata[1]:,.0f} %{customdata[0]}<br>"
                "FCF: %{customdata[2]:,.0f} %{customdata[0]}<br>"
                "Market Cap: %{customdata[3]:,.0f}<br>"
                "Cash: %{customdata[4]:,.0f}<br>"
                "Debt: %{customdata[5]:,.0f}<br>"
                "Market Cap Method: %{customdata[6]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{market.upper()} {symbol} Annual EV / FCF",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font={"color": colors["text"]},
        margin={"l": 56, "r": 24, "t": 56, "b": 48},
        xaxis={
            "title": "Fiscal Year",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
        },
        yaxis={
            "title": "EV / FCF",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
            "ticksuffix": "x",
        },
        showlegend=False,
    )
    return json.loads(fig.to_json())


def _theme_colors(theme: str) -> dict[str, str]:
    if theme == "light":
        return {
            "background": "#FFFFFF",
            "text": "#1F2937",
            "grid": "rgba(156, 163, 175, 0.35)",
            "line": "#2563EB",
        }
    return {
        "background": "#151518",
        "text": "#FFFFFF",
        "grid": "rgba(75, 85, 99, 0.35)",
        "line": "#2D9BF0",
    }
