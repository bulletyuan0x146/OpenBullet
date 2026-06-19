from __future__ import annotations

from copy import deepcopy
import json
from typing import Annotated, Literal

import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException, Query

from openbullet.providers.roic import RoicProvider
from openbullet.widgets.registry import register_widget

router = APIRouter(prefix="/equity", tags=["Equity"])
provider = RoicProvider()

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
        "name": "ROIC",
        "description": "Annual return on invested capital for A-share and Hong Kong stocks.",
        "category": "Valuation",
        "type": "table",
        "endpoint": "equity/roic",
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
                        "field": "roic",
                        "headerName": "ROIC",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 110,
                    },
                    {
                        "field": "roic_yoy_change",
                        "headerName": "ROIC YoY Change",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 160,
                    },
                    {
                        "field": "report_date",
                        "headerName": "Report Date",
                        "cellDataType": "dateString",
                        "width": 130,
                    },
                    {
                        "field": "currency",
                        "headerName": "Currency",
                        "cellDataType": "text",
                        "width": 110,
                    },
                    {
                        "field": "method",
                        "headerName": "Method",
                        "cellDataType": "text",
                        "width": 160,
                    },
                    {
                        "field": "source",
                        "headerName": "Source",
                        "cellDataType": "text",
                        "width": 280,
                    },
                ],
            }
        },
    }
)
@router.get("/roic")
def get_roic(market: MarketParam = "cn", symbol: SymbolParam = "600519") -> list[dict]:
    try:
        return provider.get_roic(market=market, symbol=symbol)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch ROIC records for {market}:{symbol}: {exc}",
        ) from exc


@register_widget(
    {
        "name": "ROIC Chart",
        "description": "Annual ROIC trend for A-share and Hong Kong stocks.",
        "category": "Valuation",
        "type": "chart",
        "endpoint": "equity/roic/chart",
        "gridData": {"w": 24, "h": 12},
        "source": ["AkShare"],
        "params": [
            deepcopy(MARKET_PARAM),
            deepcopy(SYMBOL_PARAM),
            deepcopy(THEME_PARAM),
        ],
    }
)
@router.get("/roic/chart")
def get_roic_chart(
    market: MarketParam = "cn",
    symbol: SymbolParam = "600519",
    theme: Annotated[Literal["dark", "light"], Query(description="Chart theme.")] = "dark",
) -> dict:
    try:
        rows = provider.get_roic(market=market, symbol=symbol)
        return _build_roic_chart(rows=rows, market=market, symbol=symbol, theme=theme)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build ROIC chart for {market}:{symbol}: {exc}",
        ) from exc


def _build_roic_chart(
    *, rows: list[dict], market: str, symbol: str, theme: str
) -> dict:
    chart_rows = [row for row in rows if row.get("roic") is not None]
    chart_rows = sorted(chart_rows, key=lambda row: row["fiscal_year"])
    colors = _theme_colors(theme)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[row["fiscal_year"] for row in chart_rows],
            y=[row["roic"] for row in chart_rows],
            name="ROIC",
            mode="lines+markers",
            line={"color": colors["line"], "width": 2},
            marker={"size": 8},
            customdata=[
                [
                    row.get("report_date"),
                    row.get("currency"),
                    _format_optional_percent(row.get("roic_yoy_change")),
                    row.get("method"),
                    row.get("source"),
                ]
                for row in chart_rows
            ],
            hovertemplate=(
                "%{x}<br>"
                "ROIC: %{y:.2f}%<br>"
                "Report Date: %{customdata[0]}<br>"
                "Currency: %{customdata[1]}<br>"
                "YoY Change: %{customdata[2]}<br>"
                "Method: %{customdata[3]}<br>"
                "Source: %{customdata[4]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{market.upper()} {symbol} Annual ROIC",
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
            "title": "ROIC",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
            "ticksuffix": "%",
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
            "line": "#7C3AED",
        }
    return {
        "background": "#151518",
        "text": "#FFFFFF",
        "grid": "rgba(75, 85, 99, 0.35)",
        "line": "#A78BFA",
    }


def _format_optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"
