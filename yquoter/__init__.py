# yquoter/__init__.py

import logging
from yquoter.logger import setup_logging


setup_logging(level=logging.WARNING)

from yquoter.datasource import register_source, register_tushare_module, get_stock_history, get_stock_realtime, get_stock_financials, get_stock_profile, get_stock_factors
from yquoter.indicators import *
from yquoter.cache import set_max_cache_entries

def init_cache_manager(max_entries: int = 50):
    """
    Initialize cache manager

    Args:
        max_entries: Max number of cached files, default 50
    """
    from .cache import init_cache, set_max_cache_entries
    set_max_cache_entries(max_entries)
    init_cache()
    return f"Cache manager initialized, max cache entries: {max_entries}"

# Auto-initialize cache manager with default settings
init_cache_manager()


def init_tushare(token: str = None):
    """Initialize tushare data source"""
    from .tushare_source import init_tushare as _init
    return _init(token)

# Public API exports
__all__ = [
    "init_tushare",
    "register_source",
    "register_tushare_module",
    "get_stock_history",
    "get_stock_realtime",
    "get_stock_factors",
    "get_stock_profile",
    "get_stock_financials",
    "get_ma_n",
    "get_boll_n",
    "get_max_drawdown",
    "get_vol_ratio",
    "get_newest_df_path",
    "get_rsi_n",
    "set_max_cache_entries"
]
