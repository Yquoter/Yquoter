# yquoter/tushare_source.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import datetime
import pandas as pd
from typing import Optional, List
from yquoter.exceptions import CodeFormatError, ConfigError, DataFetchError, TuShareAPIError, TuShareNotImportableError
from yquoter.logger import get_logger
from yquoter.config import REALTIME_STANDARD_FIELDS, TUSHARE_REALTIME_MAPPING
from yquoter.utils import convert_code_to_tushare, filter_fields

logger = get_logger(__name__)

_pro = None  # Global TuShare API instance
_ts_module = None # Global TuShare module instance (ts)

def _check_tushare_token(ts_module, token: str) -> bool:
    """
    Validates Tushare Token by calling a lightweight API (daily).

    Args:
        ts: The imported tushare module.
        token: The Tushare API token.

    Returns:
        True if the token is valid and connection is successful, False otherwise.
    """
    try:
        ts_module.set_token(token)
        pro = ts_module.pro_api(token)

        # Use a lightweight, low-frequency API to check connection/auth
        # Query for a single day's trade calendar
        df = pro.daily(ts_code='000001.SZ', start_date='20180701', end_date='20180718')

        if df is not None:  # Tushare usually returns a DF, even if empty
            logger.info("Tushare Token validated successfully via lightweight API.")
            return True

        # This case is unlikely if the API call succeeded, but kept for robustness
        logger.warning("Tushare API returned empty data during validation.")
    except Exception as e:
        logger.warning(f"Tushare Token verification failed. The API server may be unreachable or the token is invalid. Reason: {e}")
        raise TuShareAPIError(f"Tushare Token verification failed: {e}") from e

def init_tushare(token: str = None):
    """
    Initializes and registers the Tushare data source module.

    Performs Tushare dependency check, token validation, and module registration.

    Args:
        token: Optional Tushare API token. If None, tries to load from environment
               variables (e.g., TUSHARE_TOKEN).

    Returns:
        True if Tushare source was successfully initialized and registered.
    """
    logger.info("Attempting to initialize Tushare data source with token: {token}...")

    try:
        import tushare as ts
    except ImportError:
        raise TuShareNotImportableError

    from yquoter.config import get_tushare_token
    from yquoter.datasource import _register_tushare_module

    if token is None:
        token = get_tushare_token()

    if not token:
        logger.error("No token provided")
        raise ConfigError("TuShare Token not provided. Please pass token or set TUSHARE_TOKEN in .env/environment variables")

    try:
        if _check_tushare_token(ts, token):
            global _pro, _ts_module
            _ts_module = ts
            _pro = ts.pro_api(token)
            # Register TuShare as an available data source
            _register_tushare_module()
            logger.info("Tushare data source successfully registered.")
    except TuShareAPIError as e:
        raise

def get_pro():
    """
    Get initialized TuShare API instance.

        Returns:
            Initialized tushare.pro_api instance

        Raises:
            ValueError: If TuShare is not initialized and no token is available
    """
    if _pro is None:
        logger.error("TuShare not initialized. Must call init_tushare() first.")
        raise ConfigError("TuShare not initialized. Please call init_tushare() before fetching data.")
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

    ts = _ts_module
    if ts is None:
        raise ConfigError("Tushare module object not found (Internal state error).")

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
        logger.error(f"Unsupported market: {market}")
        raise CodeFormatError(f"Unsupported market: {market}")
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
    logger.info(f"Getting historical stock data from TuShare : {code}")
    try:
        df = _fetch_tushare(market, code, start, end, klt=klt, fqt=fqt)
    except DataFetchError as e:
        logger.error("Tushare API failed for code %s (market %s). Check token/permissions. Error: %s",
                     code, market, e)
        df = pd.DataFrame()

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
                ['code', 'name', 'datetime', 'pre_close', 'high', 'open', 'high', 'low', 'close', 'vol', 'amount']

        Raises:
            DataSourceError: If market is not supported or implementation is missing
    """
    pro = get_pro()
    ts_code = convert_code_to_tushare(code, market)
    df = pd.DataFrame()

    if market == 'cn':
        try:
            df = pro.rt_k(ts_code=ts_code)
        except DataFetchError as e:
            logger.error("Tushare API failed for code %s (market %s). Check token/permissions. Error: %s",
                         code, market, e)

    elif market in ("hk", "us"):
        logger.warning(
            "Realtime data for market '%s' (code: %s) is not implemented via the Tushare source. "
            "Returning empty DataFrame.",
            market, code
        )
    else:
        raise CodeFormatError(f"Unsupported market: {market}")

    df.rename(columns=TUSHARE_REALTIME_MAPPING, inplace=True)

    if df.empty:
        fields_to_filter = field if field is not None else REALTIME_STANDARD_FIELDS
        return pd.DataFrame(columns=fields_to_filter)

    current_date = datetime.now().strftime('%Y%m%d %H:%M')

    loc = 0
    if 'code' in df.columns:
        loc = df.columns.get_loc('code') + 1
    elif 'name' in df.columns:
        loc = df.columns.get_loc('name') + 1

    df.insert(loc=loc, column='datetime', value=current_date)

    fields_to_filter = field if field is not None else REALTIME_STANDARD_FIELDS


    return filter_fields(df, fields_to_filter)
