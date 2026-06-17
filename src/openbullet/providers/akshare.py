from __future__ import annotations

import math
import time
from typing import Any

import akshare as ak
from akshare.stock.cons import zh_sina_a_stock_payload, zh_sina_a_stock_url
from akshare.utils import demjson
import pandas as pd
import requests

from openbullet.config import settings


class AkShareProvider:
    """Adapter for AkShare market data."""

    def __init__(self) -> None:
        self._a_stock_spot_cache: tuple[float, list[dict[str, Any]]] | None = None

    def get_a_stock_spot(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        try:
            frame = self._get_a_stock_spot_frame(limit=limit)
            normalized = self._normalize_a_stock_spot(frame)
            if limit is not None and limit > 0:
                normalized = normalized.head(limit)
            rows = normalized.to_dict(orient="records")
            self._a_stock_spot_cache = (time.monotonic(), rows)
            return rows
        except Exception:
            cached_rows = self._get_cached_a_stock_spot()
            if cached_rows is not None:
                return cached_rows[:limit] if limit is not None and limit > 0 else cached_rows
            raise

    def _get_a_stock_spot_frame(self, *, limit: int | None = None) -> pd.DataFrame:
        if limit is not None and 0 < limit <= 500:
            try:
                return self._fetch_a_stock_spot_em_limited(limit=limit)
            except requests.RequestException:
                return self._fetch_a_stock_spot_sina_limited(limit=limit)
        return ak.stock_zh_a_spot_em()

    @staticmethod
    def _fetch_a_stock_spot_em_limited(*, limit: int) -> pd.DataFrame:
        urls = [
            "https://push2.eastmoney.com/api/qt/clist/get",
            "http://push2.eastmoney.com/api/qt/clist/get",
            "https://82.push2.eastmoney.com/api/qt/clist/get",
            "http://82.push2.eastmoney.com/api/qt/clist/get",
            "https://61.push2.eastmoney.com/api/qt/clist/get",
            "http://61.push2.eastmoney.com/api/qt/clist/get",
            "https://40.push2.eastmoney.com/api/qt/clist/get",
            "http://40.push2.eastmoney.com/api/qt/clist/get",
        ]
        params = {
            "pn": "1",
            "pz": str(limit),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": (
                "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,"
                "f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
            ),
        }
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
            "Referer": "https://quote.eastmoney.com/center/gridlist.html",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36"
            ),
        }
        last_error: requests.RequestException | None = None
        response: requests.Response | None = None
        for url in urls:
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=15,
                    headers=headers,
                )
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("Failed to fetch A-share realtime quotes.")

        if response is None:
            raise RuntimeError("Failed to fetch A-share realtime quotes.")

        data = response.json().get("data") or {}
        rows = data.get("diff") or []
        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame()
        frame["序号"] = range(1, len(frame) + 1)
        frame = frame.rename(
            columns={
                "f2": "最新价",
                "f3": "涨跌幅",
                "f4": "涨跌额",
                "f5": "成交量",
                "f6": "成交额",
                "f7": "振幅",
                "f8": "换手率",
                "f9": "市盈率-动态",
                "f10": "量比",
                "f11": "5分钟涨跌",
                "f12": "代码",
                "f14": "名称",
                "f15": "最高",
                "f16": "最低",
                "f17": "今开",
                "f18": "昨收",
                "f20": "总市值",
                "f21": "流通市值",
                "f23": "涨速",
                "f24": "市净率",
                "f25": "60日涨跌幅",
                "f22": "年初至今涨跌幅",
            }
        )
        numeric_columns = [
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "最高",
            "最低",
            "今开",
            "昨收",
            "量比",
            "换手率",
            "市盈率-动态",
            "市净率",
            "总市值",
            "流通市值",
            "涨速",
            "5分钟涨跌",
            "60日涨跌幅",
            "年初至今涨跌幅",
        ]
        for column in numeric_columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def _fetch_a_stock_spot_sina_limited(*, limit: int) -> pd.DataFrame:
        page_size = int(zh_sina_a_stock_payload.get("num", 80))
        page_count = max(1, math.ceil(limit / page_size))
        payload = zh_sina_a_stock_payload.copy()
        frames: list[pd.DataFrame] = []
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Connection": "close",
            "Referer": "https://vip.stock.finance.sina.com.cn/mkt/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36"
            ),
        }
        for page in range(1, page_count + 1):
            payload.update({"page": str(page)})
            response = requests.get(
                zh_sina_a_stock_url,
                params=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            rows = demjson.decode(response.text)
            frames.append(pd.DataFrame(rows))

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if frame.empty:
            return pd.DataFrame()

        frame = frame.head(limit)
        numeric_columns = {
            "trade": "float",
            "pricechange": "float",
            "changepercent": "float",
            "buy": "float",
            "sell": "float",
            "settlement": "float",
            "open": "float",
            "high": "float",
            "low": "float",
            "volume": "float",
            "amount": "float",
            "per": "float",
            "pb": "float",
            "mktcap": "float",
            "nmc": "float",
            "turnoverratio": "float",
        }
        for column in numeric_columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        frame = frame.rename(
            columns={
                "symbol": "代码",
                "name": "名称",
                "trade": "最新价",
                "pricechange": "涨跌额",
                "changepercent": "涨跌幅",
                "buy": "买入",
                "sell": "卖出",
                "settlement": "昨收",
                "open": "今开",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "ticktime": "时间戳",
                "per": "市盈率-动态",
                "pb": "市净率",
                "mktcap": "总市值",
                "nmc": "流通市值",
                "turnoverratio": "换手率",
            }
        )
        if "总市值" in frame.columns:
            frame["总市值"] = frame["总市值"] * 10000
        if "流通市值" in frame.columns:
            frame["流通市值"] = frame["流通市值"] * 10000
        return frame

    def _get_cached_a_stock_spot(self) -> list[dict[str, Any]] | None:
        if self._a_stock_spot_cache is None:
            return None

        cached_at, rows = self._a_stock_spot_cache
        cache_age = time.monotonic() - cached_at
        if cache_age > settings.akshare_a_stock_cache_ttl_seconds:
            return None
        return rows

    @staticmethod
    def _normalize_a_stock_spot(frame: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "代码": "symbol",
            "名称": "name",
            "最新价": "price",
            "涨跌幅": "change_pct",
            "涨跌额": "change",
            "成交量": "volume",
            "成交额": "turnover",
            "振幅": "amplitude",
            "最高": "high",
            "最低": "low",
            "今开": "open",
            "昨收": "previous_close",
            "量比": "volume_ratio",
            "换手率": "turnover_rate",
            "市盈率-动态": "pe_dynamic",
            "市净率": "pb",
            "总市值": "market_cap",
            "流通市值": "float_market_cap",
            "涨速": "change_speed",
            "5分钟涨跌": "change_5m",
            "60日涨跌幅": "change_pct_60d",
            "年初至今涨跌幅": "change_pct_ytd",
        }
        existing_columns = [column for column in column_map if column in frame.columns]
        normalized = frame.loc[:, existing_columns].rename(columns=column_map)
        normalized = normalized.astype(object).where(pd.notnull(normalized), None)
        return normalized
