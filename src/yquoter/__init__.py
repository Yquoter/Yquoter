# yquoter/__init__.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""Yquoter: A unified financial data interface and analysis toolkit for CN/HK/US markets."""

__version__ = "0.1.0"
__author__ = "Yodeesy"
__email__ = "yodeeshi@gmail.com"

import logging

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
from yquoter.logger import setup_logging
setup_logging(level=logging.WARNING)

# ----------------------------------------------------------------------
# Core imports
# ----------------------------------------------------------------------
from yquoter.datasource import (
    register_source,
    register_tushare_module,
    set_default_source,
    get_stock_history,
    get_stock_realtime,
    get_stock_financials,
    get_stock_profile,
    get_stock_factors,
)
from yquoter.indicators import *


# ----------------------------------------------------------------------
# Cache initialization
# ----------------------------------------------------------------------
def init_cache_manager(max_entries: int = 50):
    """
    Initialize the cache manager.

    Args:
        max_entries (int): Max number of cached files. Default is 50.
    """
    from .cache import init_cache, set_max_cache_entries
    set_max_cache_entries(max_entries)
    init_cache()
    logging.getLogger(__name__).info(
        f"Cache manager initialized, max cache entries: {max_entries}"
    )


# Auto-initialize cache (safe-guarded)
try:
    init_cache_manager()
except Exception as e:
    logging.getLogger(__name__).warning(f"Cache manager init failed: {e}")


# ----------------------------------------------------------------------
# TuShare initialization
# ----------------------------------------------------------------------
def init_tushare(token: str = None):
    """
    Initialize TuShare data source.

    Args:
        token (str, optional): TuShare API token.
    """
    from .tushare_source import init_tushare as _init
    return _init(token)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
__all__ = [
    "init_tushare",
    "register_source",
    "register_tushare_module",
    "set_default_source",
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
    "get_rv_n",
    "init_cache_manager",
]

