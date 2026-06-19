from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from typing import Annotated, Literal

import pandas as pd
import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException, Query

from openbullet.providers.dividends import DividendProvider, _to_iso_date
from openbullet.providers.prices import get_price_history
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
        "description": "Dividend yield and close price chart for A-share and Hong Kong stocks.",
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
    chart_rows = _enrich_rows_with_prices(rows=rows, market=market, symbol=symbol)
    chart_rows = [
        row
        for row in chart_rows
        if row.get("cash_dividend_per_share") is not None
        and row.get("event_dividend_yield") is not None
        and row.get("price_date")
    ]
    chart_rows = sorted(
        chart_rows,
        key=lambda row: row.get("price_date") or "",
    )

    colors = _theme_colors(theme)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[row["price_date"] for row in chart_rows],
            y=[row["event_dividend_yield"] for row in chart_rows],
            name="Dividend Yield",
            marker_color=colors["bar"],
            opacity=0.62,
            yaxis="y2",
            customdata=[
                [
                    row.get("currency"),
                    row.get("cash_dividend_per_share"),
                    row.get("close_price"),
                    row.get("announcement_date"),
                    row.get("ex_dividend_date"),
                    row.get("record_date"),
                    row.get("payment_date"),
                    row.get("status"),
                    row.get("plan_text"),
                ]
                for row in chart_rows
            ],
            hovertemplate=(
                "%{x}<br>"
                "Dividend Yield: %{y:.2%}<br>"
                "Cash / Share: %{customdata[1]} %{customdata[0]}<br>"
                "Close Price: %{customdata[2]}<br>"
                "Announcement: %{customdata[3]}<br>"
                "Ex-Date: %{customdata[4]}<br>"
                "Record: %{customdata[5]}<br>"
                "Payment: %{customdata[6]}<br>"
                "Status: %{customdata[7]}<br>"
                "Plan: %{customdata[8]}"
                "<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[row["price_date"] for row in chart_rows],
            y=[row["close_price"] for row in chart_rows],
            name="Close Price",
            mode="lines+markers",
            yaxis="y",
            line={"color": colors["line"], "width": 2},
            marker={"size": 7},
            customdata=[
                [
                    row.get("event_dividend_yield"),
                    row.get("cash_dividend_per_share"),
                    row.get("currency"),
                    row.get("plan_text"),
                ]
                for row in chart_rows
            ],
            hovertemplate=(
                "%{x}<br>"
                "Close Price: %{y}<br>"
                "Dividend Yield: %{customdata[0]:.2%}<br>"
                "Cash / Share: %{customdata[1]} %{customdata[2]}<br>"
                "Plan: %{customdata[3]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{market.upper()} {symbol} Dividend Yield and Price",
        paper_bgcolor=colors["background"],
        plot_bgcolor=colors["background"],
        font={"color": colors["text"]},
        margin={"l": 48, "r": 64, "t": 56, "b": 48},
        barmode="overlay",
        xaxis={
            "title": "Ex-Dividend Date",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
        },
        yaxis={
            "title": "Close Price",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
        },
        yaxis2={
            "title": "Dividend Yield",
            "overlaying": "y",
            "side": "right",
            "tickformat": ".1%",
            "gridcolor": colors["grid"],
            "tickfont": {"color": colors["text"]},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )
    return json.loads(fig.to_json())


def _enrich_rows_with_prices(
    *, rows: list[dict], market: str, symbol: str
) -> list[dict]:
    event_dates = [
        row.get("ex_dividend_date") or row.get("announcement_date")
        for row in rows
        if row.get("cash_dividend_per_share") is not None
        and (row.get("ex_dividend_date") or row.get("announcement_date"))
    ]
    if not event_dates:
        return rows

    parsed_dates = pd.to_datetime(event_dates, errors="coerce").dropna()
    if parsed_dates.empty:
        return rows

    start_date = (parsed_dates.min().date() - timedelta(days=7)).strftime("%Y%m%d")
    end_date = (parsed_dates.max().date() + timedelta(days=7)).strftime("%Y%m%d")
    prices = get_price_history(
        market=market,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
    if prices.empty:
        return rows

    prices = prices.sort_values("date").reset_index(drop=True)
    price_dates = pd.to_datetime(prices["date"], errors="coerce").tolist()
    enriched_rows: list[dict] = []
    for row in rows:
        enriched = row.copy()
        event_date_value = row.get("ex_dividend_date") or row.get("announcement_date")
        event_date = pd.to_datetime(event_date_value, errors="coerce")
        cash_dividend = row.get("cash_dividend_per_share")
        if pd.notna(event_date) and cash_dividend is not None:
            price_index = _find_price_index_on_or_before(price_dates, event_date)
            if price_index is not None:
                price_row = prices.iloc[price_index]
                close_price = float(price_row["close"])
                enriched["price_date"] = _to_iso_date(price_row["date"])
                enriched["close_price"] = round(close_price, 6)
                enriched["event_dividend_yield"] = round(cash_dividend / close_price, 8)
        enriched_rows.append(enriched)
    return enriched_rows


def _find_price_index_on_or_before(
    price_dates: list[pd.Timestamp], event_date: pd.Timestamp
) -> int | None:
    selected_index: int | None = None
    for index, price_date in enumerate(price_dates):
        if pd.isna(price_date):
            continue
        if price_date <= event_date:
            selected_index = index
        else:
            break
    return selected_index


def _theme_colors(theme: str) -> dict[str, str]:
    if theme == "light":
        return {
            "background": "#FFFFFF",
            "text": "#1F2937",
            "grid": "rgba(156, 163, 175, 0.35)",
            "bar": "#2563EB",
            "line": "#16A34A",
        }
    return {
        "background": "#151518",
        "text": "#FFFFFF",
        "grid": "rgba(75, 85, 99, 0.35)",
        "bar": "#2D9BF0",
        "line": "#22C55E",
    }
