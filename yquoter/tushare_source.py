# yquoter/tushare_source.py

import os
import tushare as ts
import pandas as pd
from typing import Optional, List
from yquoter.utils import convert_code_to_tushare, parse_date_str, filter_fields


_pro = None  # Global TuShare instance
_token = None  # Delayed token storage


def init_tushare(token: str = None):
    """
    Initialize TuShare interface.

        - Uses provided token if available
        - Otherwise retrieves token via get_tushare_token()

        Args:
            token: Optional TuShare API token

        Raises:
            ValueError: If no token is provided and not set in environment variables
    """
    from yquoter.config import get_tushare_token
    from yquoter.datasource import register_source

    global _pro, _token
    if token is None:
        token = get_tushare_token()

    if not token:
        raise ValueError("TuShare Token not provided. Please pass token or set TUSHARE_TOKEN in .env/environment variables")

    _token = token
    _pro = ts.pro_api(token)
    # Register TuShare as an available data source
    register_source("tushare", get_stock_history_tushare)

def get_pro():
    """
    Get initialized TuShare API instance.

        Returns:
            Initialized tushare.pro_api instance

        Raises:
            ValueError: If TuShare is not initialized and no token is available
    """
    global _pro, _token
    if _pro:
        return _pro
    if not _token:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise ValueError("TuShare not initialized. Please call init_tushare or set TUSHARE_TOKEN environment variable")
        _token = token
        _pro = ts.pro_api(_token)
    return _pro


def _fetch_tushare(market: str, code: str, start: str, end: str, klt: int=101, fqt: int=1) -> pd.DataFrame:
    """
    Internal helper function: Fetch historical data via TuShare API (different endpoints for different markets)

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code
            start: Start date in 'YYYYMMDD' format
            end: End date in 'YYYYMMDD' format
            klt: K-line type code (101=daily, 102=weekly, 103=monthly)
            fqt: Adjustment type (0=no adjustment, 1=qfq, 2=hfq)

        Returns:
            DataFrame containing historical data

        Raises:
            ValueError: If market is not supported
    """
    pro = get_pro()
    ts_code = convert_code_to_tushare(code, market)
    def _klt_to_freq(klt: int) -> str:
        """Convert klt code to TuShare frequency string"""
        return {
            101: 'D',  # Daily
            102: 'W',  # Weekly
            103: 'M',  # Monthly
        }.get(klt, 'D')

    def _fqt_to_adj(fqt: int) -> Optional[str]:
        """Convert fqt code to TuShare adjustment string"""
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
        raise ValueError(f"Unsupported market: {market}")
    return df

def get_stock_history_tushare(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1
) -> pd.DataFrame:
    """
    Get historical stock data from TuShare with caching support.

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code
            start: Start date in 'YYYYMMDD' format
            end: End date in 'YYYYMMDD' format
            klt: K-line type code (101=daily, 102=weekly, 103=monthly)
            fqt: Adjustment type (0=no adjustment, 1=qfq, 2=hfq)

        Returns:
            DataFrame containing standardized historical data
    """
    df = _fetch_tushare(market, code, start, end, klt=klt, fqt=fqt)
    if df.empty:
        return df

    # General data cleaning
    df.sort_values(df.columns[1], inplace=True)  # Sort by date column (position varies by market)
    df.reset_index(drop=True, inplace=True)
    # TODO: Unify column names across different markets
    return df

def get_stock_realtime_tushare(
        market: str,
        code: str,
        field: List[str] = None
) -> pd.DataFrame:
    """
    Get real-time stock quotes (due to TuShare limitations, some markets may return latest daily data).

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code
            field: Optional list of fields to filter results

        Returns:
            DataFrame with real-time quotes, standardized fields:
                ['datetime', 'open', 'high', 'low', 'close', 'volume']

        Raises:
            DataSourceError: If market is not supported or implementation is missing
    """
    pro = get_pro()
    ts_code = convert_code_to_tushare(code, market)

    if market == 'cn':
        df = pro.rt_k(ts_code=ts_code)
    elif market in ("hk", "us"):
        pass
    else:
        raise ValueError(f"Unsupported market: {market}")

    return filter_fields(df, field)
