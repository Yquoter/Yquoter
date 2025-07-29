# yquoter/tushare_source.py

import os
import tushare as ts
import pandas as pd
from typing import Optional
from yquoter.config import TUSHARE_TOKEN
from yquoter.utils import convert_code_to_tushare, parse_date_str
from yquoter.cache import get_cache_path, cache_exists, load_cache, save_cache

_pro = None # 全局 TuShare 实例


def init_tushare(token: str = None):
    """
    初始化 TuShare 接口。

    - 若手动传入 token，则使用之；
    - 否则默认从环境变量 `TUSHARE_TOKEN` 读取。

    Raises:
        ValueError: 如果未传入 token 且环境变量未设置。
    """
    global _pro
    if token is None:
        token = os.environ.get("TUSHARE_TOKEN")

    if not token:
        raise ValueError("TuShare Token 未提供，请传入 token 或设置环境变量 TUSHARE_TOKEN")

    _pro = ts.pro_api(token)

def get_pro():
    """返回已初始化的 TuShare 接口实例。"""
    global _pro
    if _pro:
        return _pro
    if TUSHARE_TOKEN:
        _pro = ts.pro_api(TUSHARE_TOKEN)
        return _pro
    raise ValueError("TuShare 未初始化，请调用 init_tushare 或设置 .env 中的 TUSHARE_TOKEN")

def _fetch_tushare(market: str, code: str, start: str, end: str, klt: int=101, fqt: int=1) -> pd.DataFrame:
    """
    通用内部函数：调用 TuShare API 拉取日线数据（不同市场对应不同接口名）
    """
    pro = get_pro()
    ts_code = convert_code_to_tushare(code, market)
    def _klt_to_freq(klt: int) -> str:
        return {
            101: 'D',  # 日线
            102: 'W',  # 周线
            103: 'M',  # 月线
        }.get(klt, 'D')

    def _fqt_to_adj(fqt: int) -> Optional[str]:
        return {
            0: None,
            1: 'qfq',
            2: 'hfq'
        }.get(fqt, None)

    if market == "cn":
        df = ts.pro_bar(
            ts_code=ts_code,
            start_date=start,
            end_date=end,
            freq=_klt_to_freq(klt),
            adj=_fqt_to_adj(fqt),
            asset="E"
        )
    elif market == "hk":
        df = pro.hk_daily(
            ts_code=ts_code,
            start_date=start,
            end_date=end
        )
    elif market == "us":
        df = pro.us_daily(
            ts_code=ts_code,
            start_date=start,
            end_date=end
        )
    else:
        raise ValueError(f"不支持的 market: {market}")
    return df

def get_stock_daily_tushare(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1
) -> pd.DataFrame:
    """
    带缓存的通用 TuShare 日线获取：
    - market: 'cn','hk','us'
    """
    cache_path = get_cache_path(market, code, start, end, klt, fqt)
    if cache_exists(cache_path):
        return load_cache(cache_path)

    df = _fetch_tushare(market, code, start, end, klt=klt, fqt=fqt)
    if df.empty:
        return df

    # 通用清洗（temp）
    df.sort_values(df.columns[1], inplace=True)  # trade_date 列位置视 market 而定
    df.reset_index(drop=True, inplace=True)
    # TODO: 根据不同市场统一重命名列
    save_cache(df, cache_path)
    return df
