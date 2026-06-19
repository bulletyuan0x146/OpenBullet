from __future__ import annotations

import akshare as ak
import pandas as pd


def get_price_history(
    *, market: str, symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    if market == "cn":
        frame = _get_cn_price_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    elif market == "hk":
        frame = _get_hk_price_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        return pd.DataFrame()

    if frame.empty:
        return pd.DataFrame()
    return frame.rename(columns={"日期": "date", "收盘": "close"}).loc[:, ["date", "close"]]


def cn_sina_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _get_cn_price_history(*, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        return ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
    except Exception:
        return ak.stock_zh_a_daily(
            symbol=cn_sina_symbol(symbol),
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )


def _get_hk_price_history(*, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        return ak.stock_hk_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
    except Exception:
        frame = ak.stock_hk_daily(symbol=symbol, adjust="")
        if frame.empty:
            return frame
        dates = pd.to_datetime(frame["date"], errors="coerce")
        start = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        return frame.loc[(dates >= start) & (dates <= end)].copy()
