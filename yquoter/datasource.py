# yquoter/datasource.py

import inspect
import pandas as pd
from datetime import datetime
from typing import Dict, Callable, Optional, Union, List
from yquoter.tushare_source import get_stock_daily_tushare
from yquoter.spider_source import get_stock_daily_spider
from yquoter.utils import *

# 全局注册表
_SOURCE_REGISTRY: Dict[str, Callable] = {
    "spider": get_stock_daily_spider,
    "tushare": get_stock_daily_tushare,
}
_DEFAULT_SOURCE = "spider"  # 优先爬虫

# 统一标准列, DataFrame格式要求
_REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

def _validate_dataframe(df: pd.DataFrame):
    """检查返回的 DataFrame 是否符合规范"""
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"数据源返回格式错误：缺少字段 {missing}, 需要包含 {_REQUIRED_COLUMNS}")
    return df

# 频率映射表
FREQ_TO_KLT = {
    # 日线/周线/月线
    "daily": 1, "day": 1, "d": 1,
    "weekly": 2, "week": 2, "w": 2,
    "monthly": 3, "month": 3, "m": 3,

    # 分钟级别
    "1min": 101, "1m": 101,
    "5min": 102, "5m": 102,
    "15min": 103, "15m": 103,
    "30min": 104, "30m": 104,
    "60min": 105, "60m": 105, "1h": 105,
}


def register_source(name: str, func: Callable = None):
    """注册新的数据源，支持函数式调用和装饰器写法"""
    def decorator(f: Callable):
        _SOURCE_REGISTRY[name.lower()] = f
        return f

    if func is not None:  # 普通调用
        return decorator(func)
    return decorator  # 装饰器写法

def set_default_source(name: str) -> None:
    """设置全局默认数据源"""
    global _DEFAULT_SOURCE
    name = name.lower()
    if name not in _SOURCE_REGISTRY:
        raise ValueError(f"未知数据源：{name}，可用数据源：{list(_SOURCE_REGISTRY)}")
    _DEFAULT_SOURCE = name

def get_stock_data(
    market: str,
    code: str,
    start: str,
    end: str,
    source: Optional[str] = None,
    freq: Optional[str] = None,
    klt: int = 101,
    fqt: int = 1,
    **kwargs
) -> pd.DataFrame:
    """
    统一数据接口：
    - market: 'cn','hk','us'
    - 统一数据接口
       - 默认 source = 全局默认值（spider）
       - 可用数据源： {list(_SOURCE_REGISTRY)}
    - freq: 'daily','weekly','monthly','1min','5min','15min','30min','60min'
    - data could be in YYYY-MM-DD format
    """
    market = market.lower()
    start = parse_date_str(start)
    end = parse_date_str(end)

    # 智能提示
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    delta_days = (end_dt - start_dt).days

    if freq in ("w", "weekly") and delta_days < 7:
        print("⚠️ 区间过短，可能无周K数据")
    elif freq in ("m", "monthly") and delta_days < 28:
        print("⚠️ 区间过短，可能无月K数据")

    src = (source or _DEFAULT_SOURCE).lower()
    if src not in _SOURCE_REGISTRY:
        raise ValueError(f"未知数据源：{src}，可用数据源：{list(_SOURCE_REGISTRY)}")

    # freq 优先于 klt
    if freq:
        freq = freq.lower()
        if freq not in FREQ_TO_KLT:
            raise ValueError(f"未知 freq：{freq}，可选值：{list(FREQ_TO_KLT)}")
        klt = FREQ_TO_KLT[freq]

    func = _SOURCE_REGISTRY[src]

    # 构造统一参数
    params = {
        "market": market,
        "code": code,
        "start": parse_date_str(start),
        "end": parse_date_str(end),
        "freq": freq,
        "klt": klt,
        "fqt": fqt,
        **kwargs,
    }

    # 过滤掉目标函数不支持的参数
    sig = inspect.signature(func)
    filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

    df = func(**filtered_params)

    # 校验输出
    return _validate_dataframe(df)
