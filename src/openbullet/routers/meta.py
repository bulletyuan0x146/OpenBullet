from __future__ import annotations

from fastapi import APIRouter

from openbullet.config import settings
from openbullet.widgets.registry import WIDGETS

router = APIRouter(tags=["Metadata"])

EQUITY_WIDGET_IDS = [
    "equity_dividends_chart",
    "equity_dividends",
    "equity_ev_fcf_chart",
    "equity_ev_fcf",
    "equity_roic_chart",
    "equity_roic",
]
EQUITY_SYNC_GROUPS = ["Group 1", "Group 2"]
DEFAULT_EQUITY_PARAMS = {
    "market": "cn",
    "symbol": "600519",
}


@router.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "ok",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/widgets.json")
def get_widgets() -> dict:
    return WIDGETS


@router.get("/apps.json")
def get_apps() -> list[dict]:
    return [
        {
            "name": settings.app_name,
            "img": "",
            "img_dark": "",
            "img_light": "",
            "description": "OpenBB Workspace backend for market data.",
            "allowCustomization": True,
            "tabs": {
                "china_market": {
                    "id": "china_market",
                    "name": "China Market",
                    "layout": [
                        {
                            "i": "cn_a_stock_spot",
                            "x": 0,
                            "y": 0,
                            "w": 32,
                            "h": 18,
                            "state": {
                                "params": {
                                    "limit": settings.akshare_a_stock_limit,
                                }
                            },
                        }
                    ],
                },
                "equity_analysis": {
                    "id": "equity_analysis",
                    "name": "Equity Analysis",
                    "layout": [
                        {
                            "i": "equity_dividends_chart",
                            "x": 0,
                            "y": 0,
                            "w": 40,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_ev_fcf_chart",
                            "x": 0,
                            "y": 12,
                            "w": 20,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_roic_chart",
                            "x": 20,
                            "y": 12,
                            "w": 20,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_dividends",
                            "x": 0,
                            "y": 24,
                            "w": 14,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_ev_fcf",
                            "x": 14,
                            "y": 24,
                            "w": 13,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_roic",
                            "x": 27,
                            "y": 24,
                            "w": 13,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                    ],
                },
                "dividends": {
                    "id": "dividends",
                    "name": "Dividends",
                    "layout": [
                        {
                            "i": "equity_dividends_chart",
                            "x": 0,
                            "y": 0,
                            "w": 24,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_dividends",
                            "x": 24,
                            "y": 0,
                            "w": 16,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                    ],
                },
                "valuation": {
                    "id": "valuation",
                    "name": "Valuation",
                    "layout": [
                        {
                            "i": "equity_ev_fcf_chart",
                            "x": 0,
                            "y": 0,
                            "w": 24,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_ev_fcf",
                            "x": 24,
                            "y": 0,
                            "w": 16,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_roic_chart",
                            "x": 0,
                            "y": 12,
                            "w": 24,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                        {
                            "i": "equity_roic",
                            "x": 24,
                            "y": 12,
                            "w": 16,
                            "h": 12,
                            "groups": EQUITY_SYNC_GROUPS,
                            "state": {
                                "params": DEFAULT_EQUITY_PARAMS,
                            },
                        },
                    ],
                }
            },
            "groups": [
                {
                    "name": "Group 1",
                    "type": "param",
                    "paramName": "market",
                    "widgetIds": EQUITY_WIDGET_IDS,
                    "defaultValue": DEFAULT_EQUITY_PARAMS["market"],
                },
                {
                    "name": "Group 2",
                    "type": "param",
                    "paramName": "symbol",
                    "widgetIds": EQUITY_WIDGET_IDS,
                    "defaultValue": DEFAULT_EQUITY_PARAMS["symbol"],
                },
            ],
        }
    ]
