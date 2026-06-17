from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from openbullet.config import settings
from openbullet.providers.akshare import AkShareProvider
from openbullet.widgets.registry import register_widget

router = APIRouter(prefix="/cn", tags=["China Market"])
provider = AkShareProvider()


@register_widget(
    {
        "name": "A Share Realtime Quotes",
        "description": "Realtime A-share stock quotes from AkShare.",
        "category": "China Market",
        "type": "table",
        "endpoint": "cn/a_stock_spot",
        "gridData": {"w": 32, "h": 18},
        "source": ["AkShare"],
        "params": [
            {
                "paramName": "limit",
                "value": settings.akshare_a_stock_limit,
                "label": "Limit",
                "type": "number",
                "description": "Maximum number of rows to return.",
            }
        ],
        "data": {
            "table": {
                "showAll": True,
                "columnsDefs": [
                    {
                        "field": "symbol",
                        "headerName": "Symbol",
                        "cellDataType": "text",
                        "chartDataType": "category",
                        "pinned": "left",
                        "width": 110,
                    },
                    {
                        "field": "name",
                        "headerName": "Name",
                        "cellDataType": "text",
                        "pinned": "left",
                        "width": 120,
                    },
                    {
                        "field": "price",
                        "headerName": "Price",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "width": 110,
                    },
                    {
                        "field": "change_pct",
                        "headerName": "Change %",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "renderFn": "greenRed",
                        "width": 120,
                    },
                    {
                        "field": "change",
                        "headerName": "Change",
                        "cellDataType": "number",
                        "chartDataType": "series",
                        "renderFn": "greenRed",
                        "width": 110,
                    },
                    {
                        "field": "volume",
                        "headerName": "Volume",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 130,
                    },
                    {
                        "field": "turnover",
                        "headerName": "Turnover",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 140,
                    },
                    {
                        "field": "high",
                        "headerName": "High",
                        "cellDataType": "number",
                        "width": 100,
                    },
                    {
                        "field": "low",
                        "headerName": "Low",
                        "cellDataType": "number",
                        "width": 100,
                    },
                    {
                        "field": "open",
                        "headerName": "Open",
                        "cellDataType": "number",
                        "width": 100,
                    },
                    {
                        "field": "previous_close",
                        "headerName": "Previous Close",
                        "cellDataType": "number",
                        "width": 140,
                    },
                    {
                        "field": "turnover_rate",
                        "headerName": "Turnover Rate",
                        "cellDataType": "number",
                        "width": 140,
                    },
                    {
                        "field": "pe_dynamic",
                        "headerName": "PE Dynamic",
                        "cellDataType": "number",
                        "width": 130,
                    },
                    {
                        "field": "pb",
                        "headerName": "PB",
                        "cellDataType": "number",
                        "width": 100,
                    },
                    {
                        "field": "market_cap",
                        "headerName": "Market Cap",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 150,
                    },
                    {
                        "field": "float_market_cap",
                        "headerName": "Float Market Cap",
                        "cellDataType": "number",
                        "formatterFn": "int",
                        "width": 170,
                    },
                ],
            }
        },
    }
)
@router.get("/a_stock_spot")
def get_a_stock_spot(
    limit: Annotated[
        int | None,
        Query(ge=1, le=6000, description="Maximum number of rows to return."),
    ] = None,
) -> list[dict]:
    try:
        return provider.get_a_stock_spot(limit=limit or settings.akshare_a_stock_limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch AkShare A-share realtime quotes: {exc}",
        ) from exc
