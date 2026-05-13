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
from yquoter.plugin_base import DataSource

logger = get_logger(__name__)

_pro = None  # Global TuShare API instance
_ts_module = None # Global TuShare module instance (ts)

def _check_tushare_token(ts_module, token: str) -> bool:
    """Validate Tushare Token by calling a lightweight API (daily).

    Args:
        ts_module: The imported tushare module.
        token: The Tushare API token.

    Returns:
        bool: True if the token is valid and connection is successful,
            False otherwise.
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

def init_tushare(token: str = None) -> None:
    """Initialize and register the Tushare data source module.

    Performs Tushare dependency check, token validation, and module
    registration.

    Args:
        token: Optional Tushare API token. If None, tries to load from
            environment variables (e.g., ``TUSHARE_TOKEN``).
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
    """Get the initialized TuShare API instance.

    Returns:
        Initialized ``tushare.pro_api`` instance.

    Raises:
        ConfigError: If TuShare is not initialized and no token is
            available.
    """
    if _pro is None:
        logger.error("TuShare not initialized. Must call init_tushare() first.")
        raise ConfigError("TuShare not initialized. Please call init_tushare() before fetching data.")
    return _pro

def _fetch_tushare(market: str, code: str, start: str, end: str,
                   klt: int = 101, fqt: int = 1) -> pd.DataFrame:
    """Fetch historical data via TuShare API.

    Uses different endpoints for different markets.

    Args:
        market: Market identifier (``'cn'``, ``'hk'``, ``'us'``).
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        klt: K-line type code (101=daily, 102=weekly, 103=monthly).
        fqt: Adjustment type (0=none, 1=qfq, 2=hfq).

    Returns:
        pd.DataFrame: Historical OHLCV data.

    Raises:
        CodeFormatError: If the market is not supported.
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
    fqt: int = 1,
) -> pd.DataFrame:
    """Get historical stock data from TuShare.

    Args:
        market: Market identifier (``'cn'``, ``'hk'``, ``'us'``).
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        klt: K-line type code (101=daily, 102=weekly, 103=monthly).
        fqt: Adjustment type (0=none, 1=qfq, 2=hfq).

    Returns:
        pd.DataFrame: Standardized historical OHLCV data.
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

    # Standardise column names: TuShare uses 'trade_date' -> Yquoter 'date'
    if "trade_date" in df.columns:
        df.rename(columns={"trade_date": "date"}, inplace=True)

    # Keep only the column set that Yquoter validation expects
    _STANDARD_COLS = ["date", "open", "high", "low", "close", "vol", "amount"]
    extra_cols = [c for c in _STANDARD_COLS if c in df.columns]
    return df[extra_cols] if extra_cols else df

def get_stock_realtime_tushare(
    market: str,
    code: str,
    field: List[str] = None,
) -> pd.DataFrame:
    """Get real-time stock quotes from TuShare.

    Note that for some markets TuShare may return the latest daily data
    rather than true real-time quotes.

    Args:
        market: Market identifier (``'cn'``, ``'hk'``, ``'us'``).
        code: Stock code.
        field: Optional list of fields to filter results.

    Returns:
        pd.DataFrame: Real-time quotes with standardized fields:
        ``['code', 'name', 'datetime', 'pre_close', 'high', 'open',
        'high', 'low', 'close', 'vol', 'amount']``.

    Raises:
        CodeFormatError: If the market is not supported or the
            implementation is missing.
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

    current_date = datetime.datetime.now().strftime('%Y%m%d %H:%M')

    loc = 0
    if 'code' in df.columns:
        loc = df.columns.get_loc('code') + 1
    elif 'name' in df.columns:
        loc = df.columns.get_loc('name') + 1

    df.insert(loc=loc, column='datetime', value=current_date)

    fields_to_filter = field if field is not None else REALTIME_STANDARD_FIELDS

    return filter_fields(df, fields_to_filter)


# ======================================================================
# DataSource plugin wrapper
# ======================================================================


class TushareDataSource(DataSource):
    """DataSource wrapper for the TuShare Pro API.

    Provides history and realtime data for CN markets via the TuShare
    financial data platform.  Requires initialisation via
    :func:`yquoter.init_tushare` before use.

    .. note::

       This source does **not** natively support async I/O.  The
       :meth:`get_history_async` / :meth:`get_realtime_async` methods
       inherited from :class:`DataSource` wrap the sync calls in a
       thread-pool executor, which is safe for use in async contexts.
    """

    name = "tushare"
    supported_types = {"history", "realtime"}
    supports_batch_realtime = False

    @property
    def initialization_hint(self):
        return (
            "Use yquoter.init_tushare(token) to enable the Tushare data source."
        )

    # -- history --

    def get_history(
        self,
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int = 101,
        fqt: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_history_tushare(market, code, start, end, klt=klt, fqt=fqt)

    # -- realtime --

    def get_realtime(
        self,
        market: str,
        code: str,
        fields=None,
        **kwargs,
    ) -> pd.DataFrame:
        # ``code`` is a single str (guaranteed by the dispatch layer when
        # ``supports_batch_realtime`` is ``False``).
        return get_stock_realtime_tushare(market, code, field=fields)