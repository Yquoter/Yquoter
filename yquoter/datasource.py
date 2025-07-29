# yquoter/datasource.py

import pandas as pd
from yquoter.tushare_source import get_stock_daily_tushare
from yquoter.spider_source import get_stock_daily_spider
from yquoter.utils import *

def get_stock_data(
    market: str,
    code: str,
    start: str,
    end: str,
    source: str = "tushare",
    klt: int = 101,
    fqt: int = 1,
    allow_spider: bool = True
) -> pd.DataFrame:
    """
    统一数据接口：
    - market: 'cn','hk','us'
    - source: 'tushare' | 'auto' | 'spider'
    - data could be in YYYY-MM-DD format
    """
    market = market.lower()
    source = source.lower()
    start = parse_date_str(start)
    end = parse_date_str(end)
    if source in ("tushare", "auto"):
        try:
            # 只有A股才会用到klt与fqt，tushare关于港股与美股的pro_bar接口不支持
            return get_stock_daily_tushare(market, code, start, end, klt, fqt)
        except Exception as e:
            if source == "auto" and allow_spider:
                return get_stock_daily_spider(market, code, start, end, klt, fqt)
            raise

    elif source == "spider":
        return get_stock_daily_spider(market, code, start, end)

    else:
        raise ValueError(f"不支持的数据源：{source}")
