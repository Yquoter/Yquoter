# yquoter/__init__.py

import logging
from yquoter.logger import setup_logging
setup_logging(level=logging.INFO)

from yquoter.datasource import register_source, get_stock_data

def init_tushare(token: str = None):
    from .tushare_source import init_tushare as _init
    return _init(token)

__all__ = [
    "init_tushare",
    "register_source",
    "get_stock_data",
]
