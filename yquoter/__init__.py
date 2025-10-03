# yquoter/__init__.py

import logging
from yquoter.logger import setup_logging
setup_logging(level=logging.INFO)

from yquoter.datasource import register_source, get_stock_history, get_stock_realtime
from yquoter.indicators import *

def init_tushare(token: str = None):
    from .tushare_source import init_tushare as _init
    return _init(token)

__all__ = [
    "init_tushare",
    "register_source",
    "get_stock_history",
    "get_stock_realtime",
    "get_ma_n",
    "get_amo",
    "get_boll_n",
    "get_max_drawdown",
    "get_vol_ratio",
    "get_newest_df_path",
    "get_rsi_n",
    "set_max_cache_entries"
]
