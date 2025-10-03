# yquoter/__init__.py

import logging
from yquoter.logger import setup_logging
setup_logging(level=logging.INFO)

from yquoter.datasource import register_source, get_stock_history, get_stock_realtime
from yquoter.indicators import *
from yquoter.cache import set_max_cache_entries

def init_cache_manager(max_entries: int = 4):
    """
    初始化缓存管理器

    参数:
        max_entries: 最大缓存文件数量，默认100
    """
    from .cache import init_cache, set_max_cache_entries
    set_max_cache_entries(max_entries)
    init_cache()
    return f"缓存管理器已初始化，最大缓存文件数: {max_entries}"

# 自动初始化缓存管理器（使用默认设置）
init_cache_manager()


def init_tushare(token: str = None):
    from .tushare_source import init_tushare as _init
    return _init(token)


__all__ = [
    "init_tushare",
    "register_source",
    "get_stock_history",
    "get_stock_realtime",
    "get_ma_n",
    "get_boll_n",
    "get_max_drawdown",
    "get_vol_ratio",
    "get_newest_df_path",
    "get_rsi_n",
    "set_max_cache_entries"
]
