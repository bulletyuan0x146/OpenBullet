# OpenBullet

OpenBB Workspace backend for market data. The first supported widget is an
AkShare-powered A-share realtime quotes table.

## Setup

```bash
uv sync
cp .env.example .env
uv run openbullet
```

The API starts on `http://localhost:5050` by default.

OpenBB Workspace metadata endpoints:

- `GET /widgets.json`
- `GET /apps.json`

Data endpoint:

- `GET /cn/a_stock_spot?limit=100`
