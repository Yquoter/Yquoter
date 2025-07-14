# yquoter/datasource.py

import pandas as pd
from yquoter.tushare_source import get_stock_daily_tushare
# from yquoter.spider_source import get_stock_daily_spider  # TODO:待实现

def get_stock_data(
    market: str,
    code: str,
    start: str,
    end: str,
    source: str = "tushare",
    allow_spider: bool = True
) -> pd.DataFrame:
    """
    统一数据接口：
    - market: 'cn','hk','us'
    - source: 'tushare' | 'auto' | 'spider'
    """
    market = market.lower()
    source = source.lower()
    if source in ("tushare", "auto"):
        try:
            return get_stock_daily_tushare(market, code, start, end)
        except Exception as e:
            if source == "auto" and allow_spider:
                # return get_stock_daily_spider(market, code, start, end)
                raise NotImplementedError("备用爬虫未实现")
            raise

    elif source == "spider":
        # return get_stock_daily_spider(market, code, start, end)
        raise NotImplementedError("备用爬虫未实现")

    else:
        raise ValueError(f"不支持的数据源：{source}")
