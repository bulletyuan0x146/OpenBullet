from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openbullet.config import settings
from openbullet.routers import cn_market, dividends, ev_fcf, meta, roic


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="OpenBB Workspace backend powered by AkShare and yfinance.",
        version=settings.app_version,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(meta.router)
    app.include_router(cn_market.router)
    app.include_router(dividends.router)
    app.include_router(ev_fcf.router)
    app.include_router(roic.router)
    return app


app = create_app()
