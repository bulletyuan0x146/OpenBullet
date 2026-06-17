from __future__ import annotations

from fastapi import APIRouter

from openbullet.config import settings
from openbullet.widgets.registry import WIDGETS

router = APIRouter(tags=["Metadata"])


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
                }
            },
            "groups": [],
        }
    ]
