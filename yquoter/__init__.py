# yquoter/__init__.py

import logging
from yquoter.logger import setup_logging
setup_logging(level=logging.INFO)

from yquoter.tushare_source import init_tushare
from yquoter.datasource import get_stock_data

__all__ = [
    "init_tushare",
    "get_stock_data",
]
