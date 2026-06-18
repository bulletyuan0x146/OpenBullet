from __future__ import annotations

from copy import deepcopy
import json
from typing import Annotated, Literal

import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException, Query

from openbullet.providers.dividends import DividendProvider
from openbullet.widgets.registry import register_widget

router = APIRouter(prefix="/equity", tags=["Equity"])
provider = DividendProvider()

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


@register_widget(
    {
        "name": "Dividend History",
        "description": "Historical cash dividend records for A-share and Hong Kong stocks.",
        "category": "Corporate Actions",
        "type": "table",
        "endpoint": "equity/dividends",
        "gridData": {"w": 20, "h": 12},
        "source": ["AkShare"],
        "params": [deepcopy(MARKET_PARAM), deepcopy(SYMBOL_PARAM)],
        "data": {
            "table": {
                "showAll": True,
                "columnsDefs": [
                    {
                        "field": "announcement_date",
                        "headerName": "Announcement",
                        "cellDataType": "dateString",
                        "width": 140,
                    },
                    {
                        "field": "ex_dividend_date",
                        "headerName": "Ex-Date",
                        "cellDataType": "dateString",
                        "width": 120,
                    },
                    {
                        "field": "payment_date",
                        "headerName": "Payment",
                        "cellDataType": "dateString",
                        "width": 120,
                    },
                    {
                        "field": "cash_dividend_per_share",
                        "headerName": "Cash / Share",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 140,
                    },
                    {
                        "field": "cash_dividend_per_10",
                        "headerName": "Cash / 10",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 120,
                    },
                    {
                        "field": "currency",
                        "headerName": "Currency",
                        "cellDataType": "text",
                        "width": 110,
                    },
                    {
                        "field": "dividend_yield",
                        "headerName": "Yield",
                        "cellDataType": "number",
                        "formatterFn": "percent",
                        "width": 110,
                    },
                    {
                        "field": "status",
                        "headerName": "Status",
                        "cellDataType": "text",
                        "width": 120,
                    },
                    {
                        "field": "plan_text",
                        "headerName": "Plan",
                        "cellDataType": "text",
                        "width": 260,
                    },
                    {
                        "field": "source",
                        "headerName": "Source",
                        "cellDataType": "text",
                        "width": 220,
                    },
                ],
            }
        },
    }
)
@router.get("/dividends")
def get_dividends(market: MarketParam = "cn", symbol: SymbolParam = "600519") -> list[dict]:
    try:
        return provider.get_dividends(market=market, symbol=symbol)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch dividend records for {market}:{symbol}: {exc}",
        ) from exc


@register_widget(
    {
        "name": "Dividend Chart",
        "description": "Cash dividend per share chart for A-share and Hong Kong stocks.",
        "category": "Corporate Actions",
        "type": "chart",
        "endpoint": "equity/dividends/chart",
        "gridData": {"w": 24, "h": 12},
        "source": ["AkShare"],
        "params": [
            deepcopy(MARKET_PARAM),
            deepcopy(SYMBOL_PARAM),
            {
                "paramName": "theme",
                "value": "dark",
                "label": "Theme",
                "type": "tabs",
                "description": "Chart theme.",
                "options": [
                    {"label": "Dark", "value": "dark"},
                    {"label": "Light", "value": "light"},
                ],
            },
        ],
    }
)
@router.get("/dividends/chart")
def get_dividends_chart(
    market: MarketParam = "cn",
    symbol: SymbolParam = "600519",
    theme: Annotated[Literal["dark", "light"], Query(description="Chart theme.")] = "dark",
) -> dict:
    try:
        rows = provider.get_dividends(market=market, symbol=symbol)
        return _build_dividend_chart(rows=rows, market=market, symbol=symbol, theme=theme)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to build dividend chart for {market}:{symbol}: {exc}",
        ) from exc


def _build_dividend_chart(
    *, rows: list[dict], market: str, symbol: str, theme: str
) -> dict:
    chart_rows = [
        row
        for row in rows
        if row.get("cash_dividend_per_share") is not None
        and (row.get("ex_dividend_date") or row.get("announcement_date"))
    ]
    chart_rows = sorted(
        chart_rows,
        key=lambda row: row.get("ex_dividend_date") or row.get("announcement_date") or "",
    )

    colors = _theme_colors(theme)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[row.get("ex_dividend_date") or row.get("announcement_date") for row in chart_rows],
            y=[row["cash_dividend_per_share"] for row in chart_rows],
            name="Cash Dividend / Share",
            marker_color=colors["bar"],
            customdata=[
                [
                    row.get("currency"),
                    row.get("announcement_date"),
                    row.get("record_date"),
                    row.get("payment_date"),
                    row.get("status"),
                    row.get("plan_text"),
                ]
                for row in chart_rows
            ],
            hovertemplate=(
                "%{x}<br>"
                "Cash / Share: %{y}<br>"
                "Currency: %{customdata[0]}<br>"
                "Announcement: %{customdata[1]}<br>"
                "Record: %{customdata[2]}<br>"
                "Payment: %{customdata[3]}<br>"
                "Status: %{customdata[4]}<br>"
                "Plan: %{customdata[5]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{market.upper()} {symbol} Dividend History",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font={"color": colors["text"]},
        margin={"l": 48, "r": 24, "t": 56, "b": 48},
        xaxis={
            "title": "Ex-Dividend Date",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
        },
        yaxis={
            "title": "Cash Dividend Per Share",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
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
            "bar": "#2563EB",
        }
    return {
        "background": "#151518",
        "text": "#FFFFFF",
        "grid": "rgba(75, 85, 99, 0.35)",
        "bar": "#2D9BF0",
    }
