from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any, Literal

import akshare as ak
import pandas as pd

from openbullet.config import settings

Market = Literal["cn", "hk"]


class DividendProvider:
    """Fetches and normalizes dividend records for CN A-shares and HK stocks."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

    def get_dividends(self, *, market: Market, symbol: str) -> list[dict[str, Any]]:
        normalized_market = market.lower()
        normalized_symbol = self._normalize_symbol(market=normalized_market, symbol=symbol)
        cache_key = (normalized_market, normalized_symbol)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if normalized_market == "cn":
            rows = self._get_cn_dividends(symbol=normalized_symbol)
        elif normalized_market == "hk":
            rows = self._get_hk_dividends(symbol=normalized_symbol)
        else:
            raise ValueError("market must be 'cn' or 'hk'")

        rows = self._sort_rows(rows)
        self._cache[cache_key] = (time.monotonic(), rows)
        return rows

    def _get_cn_dividends(self, *, symbol: str) -> list[dict[str, Any]]:
        try:
            frame = ak.stock_fhps_detail_em(symbol=symbol)
            return self._normalize_cn_em(frame=frame, symbol=symbol)
        except Exception:
            frame = ak.stock_dividend_cninfo(symbol=symbol)
            return self._normalize_cn_cninfo(frame=frame, symbol=symbol)

    def _get_hk_dividends(self, *, symbol: str) -> list[dict[str, Any]]:
        try:
            frame = ak.stock_hk_dividend_payout_em(symbol=symbol)
            return self._normalize_hk_em(frame=frame, symbol=symbol)
        except Exception:
            frame = ak.stock_hk_fhpx_detail_ths(symbol=symbol[-4:])
            return self._normalize_hk_ths(frame=frame, symbol=symbol)

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

    @staticmethod
    def _normalize_cn_em(*, frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            cash_per_10 = _to_float(item.get("现金分红-现金分红比例"))
            rows.append(
                {
                    "symbol": symbol,
                    "market": "cn",
                    "fiscal_year": _year_from_value(item.get("报告期")),
                    "announcement_date": _to_iso_date(item.get("最新公告日期"))
                    or _to_iso_date(item.get("业绩披露日期")),
                    "record_date": _to_iso_date(item.get("股权登记日")),
                    "ex_dividend_date": _to_iso_date(item.get("除权除息日")),
                    "payment_date": None,
                    "cash_dividend_per_share": _round_optional(
                        cash_per_10 / 10 if cash_per_10 is not None else None
                    ),
                    "cash_dividend_per_10": _round_optional(cash_per_10),
                    "currency": "CNY",
                    "bonus_share_per_10": _round_optional(
                        _to_float(item.get("送转股份-送股比例"))
                    ),
                    "transfer_share_per_10": _round_optional(
                        _to_float(item.get("送转股份-转股比例"))
                    ),
                    "dividend_yield": _round_optional(
                        _to_float(item.get("现金分红-股息率"))
                    ),
                    "status": _clean_text(item.get("方案进度")),
                    "plan_text": _clean_text(item.get("现金分红-现金分红比例描述")),
                    "source": "akshare:stock_fhps_detail_em",
                }
            )
        return rows

    @staticmethod
    def _normalize_cn_cninfo(
        *, frame: pd.DataFrame, symbol: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            cash_per_10 = _to_float(item.get("派息比例"))
            rows.append(
                {
                    "symbol": symbol,
                    "market": "cn",
                    "fiscal_year": _year_from_text(item.get("报告时间")),
                    "announcement_date": _to_iso_date(item.get("实施方案公告日期")),
                    "record_date": _to_iso_date(item.get("股权登记日")),
                    "ex_dividend_date": _to_iso_date(item.get("除权日")),
                    "payment_date": _to_iso_date(item.get("派息日")),
                    "cash_dividend_per_share": _round_optional(
                        cash_per_10 / 10 if cash_per_10 is not None else None
                    ),
                    "cash_dividend_per_10": _round_optional(cash_per_10),
                    "currency": "CNY",
                    "bonus_share_per_10": _round_optional(_to_float(item.get("送股比例"))),
                    "transfer_share_per_10": _round_optional(
                        _to_float(item.get("转增比例"))
                    ),
                    "dividend_yield": None,
                    "status": _clean_text(item.get("分红类型")),
                    "plan_text": _clean_text(item.get("实施方案分红说明")),
                    "source": "akshare:stock_dividend_cninfo",
                }
            )
        return rows

    @staticmethod
    def _normalize_hk_em(*, frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            plan_text = _clean_text(item.get("分红方案"))
            cash_per_share, currency = _parse_hk_cash_dividend(plan_text)
            rows.append(
                {
                    "symbol": symbol,
                    "market": "hk",
                    "fiscal_year": _clean_text(item.get("财政年度")),
                    "announcement_date": _to_iso_date(item.get("最新公告日期")),
                    "record_date": None,
                    "ex_dividend_date": _to_iso_date(item.get("除净日")),
                    "payment_date": _to_iso_date(item.get("发放日")),
                    "cash_dividend_per_share": _round_optional(cash_per_share),
                    "cash_dividend_per_10": _round_optional(
                        cash_per_share * 10 if cash_per_share is not None else None
                    ),
                    "currency": currency,
                    "bonus_share_per_10": None,
                    "transfer_share_per_10": None,
                    "dividend_yield": None,
                    "status": _clean_text(item.get("分配类型")),
                    "plan_text": plan_text,
                    "source": "akshare:stock_hk_dividend_payout_em",
                }
            )
        return rows

    @staticmethod
    def _normalize_hk_ths(*, frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in frame.to_dict(orient="records"):
            plan_text = _clean_text(item.get("方案"))
            if not plan_text or "不分红" in plan_text:
                continue
            cash_per_share, currency = _parse_hk_cash_dividend(plan_text)
            rows.append(
                {
                    "symbol": symbol,
                    "market": "hk",
                    "fiscal_year": _clean_text(item.get("类型")),
                    "announcement_date": _to_iso_date(item.get("公告日期")),
                    "record_date": None,
                    "ex_dividend_date": _to_iso_date(item.get("除净日")),
                    "payment_date": _to_iso_date(item.get("派息日")),
                    "cash_dividend_per_share": _round_optional(cash_per_share),
                    "cash_dividend_per_10": _round_optional(
                        cash_per_share * 10 if cash_per_share is not None else None
                    ),
                    "currency": currency,
                    "bonus_share_per_10": None,
                    "transfer_share_per_10": None,
                    "dividend_yield": None,
                    "status": _clean_text(item.get("进度")),
                    "plan_text": plan_text,
                    "source": "akshare:stock_hk_fhpx_detail_ths",
                }
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

    @staticmethod
    def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            rows,
            key=lambda row: (
                row.get("ex_dividend_date")
                or row.get("announcement_date")
                or row.get("payment_date")
                or ""
            ),
            reverse=True,
        )


def _to_iso_date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nat", "nan", "none"}:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


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


def _year_from_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (date, datetime)):
        return str(value.year)
    match = re.search(r"(19|20)\d{2}", str(value))
    return match.group(0) if match else None


def _year_from_text(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    match = re.search(r"(19|20)\d{2}", text)
    return match.group(0) if match else text


def _parse_hk_cash_dividend(plan_text: str | None) -> tuple[float | None, str]:
    if not plan_text:
        return None, "HKD"

    currency = "HKD"
    if "人民币" in plan_text:
        currency = "CNY"
    elif "美元" in plan_text:
        currency = "USD"

    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:元|港元|港币)", plan_text)
    if match is None:
        return None, currency
    return float(match.group(1)), currency
