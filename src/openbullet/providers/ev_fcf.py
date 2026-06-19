from __future__ import annotations

import time
from datetime import date, datetime
from typing import Any, Literal

import akshare as ak
import pandas as pd

from openbullet.config import settings
from openbullet.providers.dividends import _to_iso_date
from openbullet.providers.prices import get_price_history

Market = Literal["cn", "hk"]

CN_DEBT_FIELDS = [
    "SHORT_LOAN",
    "NONCURRENT_LIAB_1YEAR",
    "LONG_LOAN",
    "BOND_PAYABLE",
    "LEASE_LIAB",
    "SHORT_BOND_PAYABLE",
    "SHORT_FIN_PAYABLE",
]
HK_DEBT_ITEMS = [
    "融资租赁负债(流动)",
    "融资租赁负债(非流动)",
    "其他金融负债(流动)",
    "其他金融负债(非流动)",
]
HK_CAPEX_ITEMS = ["购建固定资产", "购建无形资产及其他资产"]


class EvFcfProvider:
    """Calculates annual EV/FCF for CN A-shares and HK stocks."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}

    def get_ev_fcf(self, *, market: Market, symbol: str) -> list[dict[str, Any]]:
        normalized_market = market.lower()
        normalized_symbol = self._normalize_symbol(market=normalized_market, symbol=symbol)
        cache_key = (normalized_market, normalized_symbol)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if normalized_market == "cn":
            rows = self._get_cn_ev_fcf(symbol=normalized_symbol)
        elif normalized_market == "hk":
            rows = self._get_hk_ev_fcf(symbol=normalized_symbol)
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

    def _get_cn_ev_fcf(self, *, symbol: str) -> list[dict[str, Any]]:
        ak_symbol = _cn_em_symbol(symbol)
        cash_flow = ak.stock_cash_flow_sheet_by_yearly_em(symbol=ak_symbol)
        balance = ak.stock_balance_sheet_by_yearly_em(symbol=ak_symbol)

        cash_flow_by_year = _records_by_report_year(cash_flow)
        balance_by_year = _records_by_report_year(balance)
        years = sorted(set(cash_flow_by_year) & set(balance_by_year), reverse=True)
        if not years:
            return []

        price_by_year = _year_end_prices(
            market="cn",
            symbol=symbol,
            years=years,
        )
        rows: list[dict[str, Any]] = []
        for year in years:
            cash_row = cash_flow_by_year[year]
            balance_row = balance_by_year[year]
            operating_cash_flow = _to_float(cash_row.get("NETCASH_OPERATE"))
            capex = _to_float(cash_row.get("CONSTRUCT_LONG_ASSET"))
            free_cash_flow = _subtract(operating_cash_flow, capex)
            cash = _to_float(balance_row.get("MONETARYFUNDS"))
            total_debt = _sum_fields(balance_row, CN_DEBT_FIELDS)
            share_capital = _to_float(balance_row.get("SHARE_CAPITAL"))
            close_price = price_by_year.get(year)
            market_cap = _multiply(close_price, share_capital)
            enterprise_value = _enterprise_value(
                market_cap=market_cap,
                total_debt=total_debt,
                cash=cash,
            )
            rows.append(
                _build_row(
                    market="cn",
                    symbol=symbol,
                    fiscal_year=year,
                    report_date=_to_iso_date(balance_row.get("REPORT_DATE")),
                    currency="CNY",
                    close_price=close_price,
                    share_capital=share_capital,
                    market_cap=market_cap,
                    cash=cash,
                    total_debt=total_debt,
                    enterprise_value=enterprise_value,
                    operating_cash_flow=operating_cash_flow,
                    capex=capex,
                    free_cash_flow=free_cash_flow,
                    financial_currency="CNY",
                    market_cap_currency="CNY",
                    market_cap_method="year_end_close_x_share_capital",
                    source="akshare:stock_cash_flow_sheet_by_yearly_em,stock_balance_sheet_by_yearly_em",
                )
            )
        return rows

    def _get_hk_ev_fcf(self, *, symbol: str) -> list[dict[str, Any]]:
        cash_flow = ak.stock_financial_hk_report_em(
            stock=symbol,
            symbol="现金流量表",
            indicator="年度",
        )
        balance = ak.stock_financial_hk_report_em(
            stock=symbol,
            symbol="资产负债表",
            indicator="年度",
        )
        indicators = ak.stock_financial_hk_analysis_indicator_em(
            symbol=symbol,
            indicator="年度",
        )

        cash_flow_by_year = _hk_records_by_year(cash_flow)
        balance_by_year = _hk_records_by_year(balance)
        indicators_by_year = _records_by_report_year(indicators)
        years = sorted(set(cash_flow_by_year) & set(balance_by_year), reverse=True)
        if not years:
            return []

        price_by_year = _year_end_prices(
            market="hk",
            symbol=symbol,
            years=years,
        )
        rows: list[dict[str, Any]] = []
        for year in years:
            cash_items = cash_flow_by_year[year]
            balance_items = balance_by_year[year]
            indicator_row = indicators_by_year.get(year, {})
            operating_cash_flow = _to_float(cash_items.get("经营业务现金净额"))
            capex = _sum_item_values(cash_items, HK_CAPEX_ITEMS)
            free_cash_flow = _subtract(operating_cash_flow, capex)
            cash = _to_float(balance_items.get("现金及等价物"))
            total_debt = _sum_item_values(balance_items, HK_DEBT_ITEMS)
            shareholder_equity = _to_float(balance_items.get("股东权益"))
            bps = _to_float(indicator_row.get("BPS"))
            share_capital = _divide(shareholder_equity, bps)
            close_price = price_by_year.get(year)
            market_cap = _multiply(close_price, share_capital)
            enterprise_value = _enterprise_value(
                market_cap=market_cap,
                total_debt=total_debt,
                cash=cash,
            )
            rows.append(
                _build_row(
                    market="hk",
                    symbol=symbol,
                    fiscal_year=year,
                    report_date=f"{year}-12-31",
                    currency="HKD",
                    close_price=close_price,
                    share_capital=share_capital,
                    market_cap=market_cap,
                    cash=cash,
                    total_debt=total_debt,
                    enterprise_value=enterprise_value,
                    operating_cash_flow=operating_cash_flow,
                    capex=capex,
                    free_cash_flow=free_cash_flow,
                    financial_currency="HKD",
                    market_cap_currency="HKD",
                    market_cap_method="year_end_close_x_shareholder_equity_div_bps",
                    source="akshare:stock_financial_hk_report_em",
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
    fiscal_year: str,
    report_date: str | None,
    currency: str,
    close_price: float | None,
    share_capital: float | None,
    market_cap: float | None,
    cash: float | None,
    total_debt: float | None,
    enterprise_value: float | None,
    operating_cash_flow: float | None,
    capex: float | None,
    free_cash_flow: float | None,
    financial_currency: str,
    market_cap_currency: str,
    market_cap_method: str,
    source: str,
) -> dict[str, Any]:
    currency_mismatch = financial_currency != market_cap_currency
    ev_to_fcf = None
    if not currency_mismatch and enterprise_value is not None and free_cash_flow:
        ev_to_fcf = enterprise_value / free_cash_flow

    return {
        "symbol": symbol,
        "market": market,
        "fiscal_year": fiscal_year,
        "report_date": report_date,
        "currency": currency,
        "close_price": _round_optional(close_price),
        "share_capital": _round_optional(share_capital),
        "market_cap": _round_optional(market_cap),
        "cash": _round_optional(cash),
        "total_debt": _round_optional(total_debt),
        "enterprise_value": _round_optional(enterprise_value),
        "operating_cash_flow": _round_optional(operating_cash_flow),
        "capex": _round_optional(capex),
        "free_cash_flow": _round_optional(free_cash_flow),
        "ev_to_fcf": _round_optional(ev_to_fcf),
        "basis": "annual",
        "market_cap_method": market_cap_method,
        "financial_currency": financial_currency,
        "market_cap_currency": market_cap_currency,
        "currency_mismatch": currency_mismatch,
        "source": source,
    }


def _cn_em_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"SH{symbol}"
    return f"SZ{symbol}"


def _records_by_report_year(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for row in frame.to_dict(orient="records"):
        report_date = pd.to_datetime(row.get("REPORT_DATE"), errors="coerce")
        if pd.isna(report_date):
            continue
        year = str(report_date.year)
        if report_date.month == 12 and report_date.day == 31:
            records.setdefault(year, row)
    return records


def _hk_records_by_year(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    records: dict[str, dict[str, float]] = {}
    for row in frame.to_dict(orient="records"):
        report_date = pd.to_datetime(row.get("REPORT_DATE"), errors="coerce")
        item_name = row.get("STD_ITEM_NAME")
        amount = _to_float(row.get("AMOUNT"))
        if pd.isna(report_date) or item_name is None or amount is None:
            continue
        if report_date.month != 12 or report_date.day != 31:
            continue
        records.setdefault(str(report_date.year), {})[str(item_name)] = amount
    return records


def _year_end_prices(
    *, market: str, symbol: str, years: list[str]
) -> dict[str, float]:
    if not years:
        return {}

    start_year = min(int(year) for year in years)
    end_year = max(int(year) for year in years)
    prices = get_price_history(
        market=market,
        symbol=symbol,
        start_date=f"{start_year}0101",
        end_date=f"{end_year}1231",
    )
    if prices.empty:
        return {}

    prices = prices.sort_values("date").reset_index(drop=True)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    result: dict[str, float] = {}
    for year in years:
        year_end = pd.Timestamp(date(int(year), 12, 31))
        year_prices = prices.loc[prices["date"] <= year_end]
        if year_prices.empty:
            continue
        price_row = year_prices.iloc[-1]
        close_price = _to_float(price_row.get("close"))
        if close_price is not None:
            result[year] = close_price
    return result


def _sum_fields(row: dict[str, Any], fields: list[str]) -> float:
    total = 0.0
    for field in fields:
        value = _to_float(row.get(field))
        if value is not None:
            total += value
    return total


def _sum_item_values(items: dict[str, float], names: list[str]) -> float:
    total = 0.0
    for name in names:
        value = _to_float(items.get(name))
        if value is not None:
            total += value
    return total


def _enterprise_value(
    *, market_cap: float | None, total_debt: float | None, cash: float | None
) -> float | None:
    if market_cap is None or total_debt is None or cash is None:
        return None
    return market_cap + total_debt - cash


def _subtract(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _multiply(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left * right


def _divide(left: float | None, right: float | None) -> float | None:
    if left is None or right in (None, 0):
        return None
    return left / right


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_optional(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)
