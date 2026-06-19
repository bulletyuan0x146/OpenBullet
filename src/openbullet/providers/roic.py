from __future__ import annotations

import time
from typing import Any, Literal

import akshare as ak
import pandas as pd

from openbullet.config import settings
from openbullet.providers.dividends import _to_iso_date

Market = Literal["cn", "hk"]


class RoicProvider:
    """Fetches annual ROIC records for CN A-shares and HK stocks."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

    def get_roic(self, *, market: Market, symbol: str) -> list[dict[str, Any]]:
        normalized_market = market.lower()
        normalized_symbol = self._normalize_symbol(market=normalized_market, symbol=symbol)
        cache_key = (normalized_market, normalized_symbol)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if normalized_market == "cn":
            rows = self._get_cn_roic(symbol=normalized_symbol)
        elif normalized_market == "hk":
            rows = self._get_hk_roic(symbol=normalized_symbol)
        else:
            raise ValueError("market must be 'cn' or 'hk'")

        rows = sorted(rows, key=lambda row: row["report_date"], reverse=True)
        self._cache[cache_key] = (time.monotonic(), rows)
        return rows

    def _get_cached(
        self, cache_key: tuple[str, str]
    ) -> list[dict[str, Any]] | None:
        cached = self._cache.get(cache_key)
        if cached is None:
            return None

        cached_at, rows = cached
        if time.monotonic() - cached_at > settings.dividend_cache_ttl_seconds:
            return None
        return rows

    def _get_cn_roic(self, *, symbol: str) -> list[dict[str, Any]]:
        frame = ak.stock_financial_analysis_indicator_em(
            symbol=_cn_analysis_symbol(symbol),
            indicator="按报告期",
        )
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            report_date = pd.to_datetime(item.get("REPORT_DATE"), errors="coerce")
            if pd.isna(report_date) or report_date.month != 12 or report_date.day != 31:
                continue

            rows.append(
                _build_row(
                    market="cn",
                    symbol=symbol,
                    name=item.get("SECURITY_NAME_ABBR"),
                    fiscal_year=str(report_date.year),
                    report_date=_to_iso_date(report_date),
                    currency=item.get("CURRENCY") or "CNY",
                    roic=_to_float(item.get("ROIC")),
                    roic_yoy_change=_to_float(item.get("ROICTZ")),
                    source="akshare:stock_financial_analysis_indicator_em",
                )
            )
        return rows

    def _get_hk_roic(self, *, symbol: str) -> list[dict[str, Any]]:
        frame = ak.stock_financial_hk_analysis_indicator_em(
            symbol=symbol,
            indicator="年度",
        )
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            report_date = pd.to_datetime(item.get("REPORT_DATE"), errors="coerce")
            if pd.isna(report_date):
                continue

            rows.append(
                _build_row(
                    market="hk",
                    symbol=symbol,
                    name=item.get("SECURITY_NAME_ABBR"),
                    fiscal_year=str(report_date.year),
                    report_date=_to_iso_date(report_date),
                    currency=item.get("CURRENCY") or "HKD",
                    roic=_to_float(item.get("ROIC_YEARLY")),
                    roic_yoy_change=None,
                    source="akshare:stock_financial_hk_analysis_indicator_em",
                )
            )
        return rows

    @staticmethod
    def _normalize_symbol(*, market: str, symbol: str) -> str:
        cleaned = symbol.strip().upper()
        for prefix in ("SH", "SZ", "BJ", "HK"):
            cleaned = cleaned.removeprefix(prefix)
        cleaned = cleaned.replace(".", "")
        if market == "cn":
            return cleaned.zfill(6)
        if market == "hk":
            return cleaned.zfill(5)
        return cleaned


def _build_row(
    *,
    market: str,
    symbol: str,
    name: Any,
    fiscal_year: str,
    report_date: str | None,
    currency: Any,
    roic: float | None,
    roic_yoy_change: float | None,
    source: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market": market,
        "name": _clean_text(name),
        "fiscal_year": fiscal_year,
        "report_date": report_date,
        "currency": _clean_text(currency),
        "roic": _round_optional(roic),
        "roic_yoy_change": _round_optional(roic_yoy_change),
        "basis": "annual",
        "method": "provider_reported",
        "source": source,
    }


def _cn_analysis_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SH"
    if symbol.startswith(("4", "8")):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_optional(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
