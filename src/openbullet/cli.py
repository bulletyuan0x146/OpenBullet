from __future__ import annotations

import uvicorn

from openbullet.config import settings


def main() -> None:
    uvicorn.run(
        "openbullet.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )
