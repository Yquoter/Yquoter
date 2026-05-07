# yquoter/datasource.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import inspect
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Callable, Optional, Union
from yquoter.cache import get_cache_path, cache_exists, load_cache, save_cache
from yquoter.spider_source import get_stock_history_spider, get_stock_realtime_spider, get_stock_financials_spider, get_stock_profile_spider, get_stock_factors_spider
from yquoter.exceptions import DataSourceError, ParameterError, DataFetchError
from yquoter.logger import get_logger
from yquoter.config import modify_df_path
from yquoter.utils import _validate_dataframe, parse_date_str

# Global registry for data sources:
# Structure: {source_name: {function_type: function_callable}}
_SOURCE_REGISTRY: Dict[str, Dict[str, Callable]] = {
    "spider": {
        "history": get_stock_history_spider,
        "realtime": get_stock_realtime_spider,
        "financials": get_stock_financials_spider,
        "profile": get_stock_profile_spider,
        "factors": get_stock_factors_spider,
    }
}
_DEFAULT_SOURCE = "spider"  # Spider source takes priority
logger = get_logger(__name__)

def register_source(source_name: str, func_type: str,
                    func: Callable = None):
    """Register a function type for a data source.

    Can be used as a decorator or a regular function call. Prompts the user
    for confirmation if an existing function is about to be overwritten in
    an interactive session.

    Args:
        source_name: Name of the data source (e.g., 'tushare').
        func_type: Type of function to register (e.g., 'realtime',
            'history').
        func: The callable function to register. If ``None``, this
            operates as a decorator.

    Returns:
        Callable: The registered function (or decorator wrapper).
    """
    from yquoter.utils import _is_interactive_session
    source_name = source_name.lower()
    func_type = func_type.lower()

    def decorator(f: Callable):
        if source_name not in _SOURCE_REGISTRY:
            _SOURCE_REGISTRY[source_name] = {}

        # Check if the function type is already registered for this source
        if func_type in _SOURCE_REGISTRY[source_name]:

            old_func_name = _SOURCE_REGISTRY[source_name][func_type].__name__
            new_func_name = f.__name__

            overwrite_allowed = False

            if _is_interactive_session():
                logger.warning(
                    f"Overwrite detected for source '{source_name}' function type '{func_type}'. "
                    f"Old: {old_func_name}, New: {new_func_name}"
                )

                # Use standard input() for user confirmation
                try:
                    user_input = input("Overwrite? [y/n]: ").lower()
                    if user_input == 'y':
                        overwrite_allowed = True
                except EOFError:
                    # Handle cases where input is redirected or closed unexpectedly
                    logger.warning("Non-interactive input detected; skipping overwrite.")
            else:
                logger.warning(
                    f"Source '{source_name}' function type '{func_type}' is already registered "
                    f"but running in a non-interactive session. Overwriting is disabled to prevent accidental changes."
                )
                # We implicitly set overwrite_allowed = False by skipping the interactive prompt

            if not overwrite_allowed:
                # If overwrite is not allowed (user said 'n' or non-interactive failure)
                logger.info(f"Overwrite cancelled. Retaining old function: {old_func_name}")
                return _SOURCE_REGISTRY[source_name][func_type]  # Return the old function instead of the new one

        # If allowed to overwrite OR if it's a new registration
        _SOURCE_REGISTRY[source_name][func_type] = f
        logger.info(f"Source '{source_name}' registered for function type '{func_type}': {f.__name__}")
        return f

    if func is not None:  # Regular function call
        return decorator(func)

    return decorator  # Decorator usage

def _register_tushare_module() -> None:
    """Register all available Tushare functions into the source registry.

    Adds the 'tushare' data source with its supported function types
    (e.g., 'history', 'realtime') to the global ``_SOURCE_REGISTRY``.
    """
    from yquoter.tushare_source import get_stock_history_tushare, get_stock_realtime_tushare
    if "tushare" not in _SOURCE_REGISTRY:
        _SOURCE_REGISTRY["tushare"] = {
        "history": get_stock_history_tushare,
        "realtime": get_stock_realtime_tushare,
        }
        logger.info(f"Source 'tushare' registered")
    else:
        logger.warning(f"Source 'tushare' already registered")
    return

def set_default_source(name: str) -> None:
    """Set the global default data source.

    Args:
        name: Name of the data source to set as default.
            Case-insensitive.

    Raises:
        DataSourceError: If the specified data source is not registered.
    """
    global _DEFAULT_SOURCE
    name = name.lower()
    if name not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {name}; available sources: {list(_SOURCE_REGISTRY)}")
    _DEFAULT_SOURCE = name
    logger.info(f"Default data source set to: {name}")


def _get_stock_history(
    market: str,
    code: str,
    start: str = None,
    end: str = None,
    klt: Union[str, int] = 101,
    fqt: int = 1,
    fields: str = "basic",
    source: Optional[str] = None,
    **kwargs
) -> pd.DataFrame:
    """Unified interface for fetching stock historical data.

    Handles cache checking, data fetching from the specified source,
    and result validation.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code.
        start: Start date. Supports ``YYYY-MM-DD`` format (auto-parsed).
        end: End date. Supports ``YYYY-MM-DD`` format (auto-parsed).
        source: Data source to use. Defaults to the global default.
        klt: K-line type code (101=daily, 102=weekly, 103=monthly).
            Default is 101.
        fqt: Forward/factor adjustment type. Default is 1.
        fields: Data field set (``"basic"`` or ``"full"``).
            Default is ``"basic"``.
        **kwargs: Additional parameters passed to the data source function.

    Returns:
        pd.DataFrame: Validated historical stock data.

    Raises:
        DataSourceError: If the data source is invalid or uninitialized.
        ParameterError: If an invalid frequency parameter is provided.
        DataFetchError: If data fetching fails.
        DataFormatError: If the returned data format is invalid.
        DateFormatError: If a date string cannot be parsed.
    """
    if start is None and end is None:
        start = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        end = datetime.now().strftime('%Y%m%d')
    elif start is None and end is not None:
        end = parse_date_str(end)
        start = (datetime.strptime(end, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
    elif end is None and start is not None:
        start = parse_date_str(start)
        end = datetime.now().strftime('%Y%m%d')
    from yquoter.config import FREQ_TO_KLT
    market = market.lower()
    # Parse date strings (DateFormatError thrown if format is invalid)
    start = parse_date_str(start)
    end = parse_date_str(end)
    logger.info(f"Fetching data for {market}:{code} from {start} to {end}")
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    delta_days = (end_dt - start_dt).days

    src = (source or _DEFAULT_SOURCE).lower()
    logger.info(f"Using data source: {src}")
    # Check TuShare availability (if selected)
    if src == "tushare" and "tushare" not in _SOURCE_REGISTRY:
        raise DataSourceError(
            "TuShare data source not enabled. Please initialize and register TuShare first with `yquoter.init_tushare(token)`, "
            "or use source='spider' instead."
        )

    # Validate selected data source
    if src not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {src}; available sources: {list(_SOURCE_REGISTRY)}")

    # Override klt with freq if freq is provided
    if klt:
        if isinstance(klt, str):
            klt = klt.lower()
            if klt not in FREQ_TO_KLT:
                raise ParameterError(f"Unknown frequency: {klt}; available values: {list(FREQ_TO_KLT)}")
            klt = FREQ_TO_KLT[klt]
            logger.info(f"Frequency converted to klt: {klt}")

    # --- Cache & Data Fetch Logic ---

    # 1. Check cache first
    cache_path = get_cache_path(market, code, start, end, klt, fqt)
    if cache_exists(cache_path):
        df_cache = load_cache(cache_path)
        if df_cache is not None and not df_cache.empty:
            logger.info(f"Returning data from cache hit: {cache_path}")
            modify_df_path(cache_path)
            return _validate_dataframe(df_cache, fields)

    # 2. Fetch from real-time source if cache missing/failed
    logger.info(f"No cache hit; fetching data from real-time source '{src}'")

    func_type = "history"
    if func_type not in _SOURCE_REGISTRY[src]:
        raise DataSourceError(f"Data source '{src}' does not support '{func_type}' data.")
    func = _SOURCE_REGISTRY[src][func_type]

    # Construct unified parameters
    params = {
        "market": market,
        "code": code,
        "start": start,
        "end": end,
        "klt": klt,
        "fqt": fqt,
        "fields": fields,
        **kwargs,
    }

    # Filter out parameters not supported by the target function
    sig = inspect.signature(func)
    filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

    try:
        # Fetch data
        logger.info(f"Calling data source function with parameters: market={market}, code={code}, klt={klt}")
        df = func(**filtered_params)

    except Exception as e:
        logger.error(f"Failed to fetch data from source '{src}': {e}")
        raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    # 3. Save to cache if data is valid
    if df is not None and not df.empty:
        logger.info(f"Successfully fetched {len(df)} records from {src}")
        save_cache(cache_path, df)  # CacheSaveError thrown if save fails
        logger.info(f"Data cached to: {cache_path}")
        modify_df_path(cache_path)

    # 4. Validate and return data
    return _validate_dataframe(df, fields)


def _get_stock_realtime(
        market: str,
        code: Union[str, list[str]],
        fields: Union[str, list[str]] = None,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """Unified interface for fetching real-time stock quotes.

    Supports batch queries for sources that support them, and falls back
    to individual queries for sources like Tushare that require
    single-code calls.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code(s) to fetch. Can be a single string or a list.
        fields: List of fields to filter in the results.
        source: Data source to use (e.g., 'tushare', 'spider').
        **kwargs: Additional keyword arguments for the source function.

    Returns:
        pd.DataFrame: Standardized real-time quotes.

    Raises:
        DataSourceError: If the source is unknown or uninitialized.
        DataFetchError: If data fetching fails.
    """

    market = market.lower()

    # 1. Standardize codes and fields to lists
    if isinstance(code, str):
        code = [code]
    if isinstance(fields, str):
        fields = [fields]

    logger.info(f"Initiating real-time data fetch for {market} with {len(code)} code(s).")

    src = (source or _DEFAULT_SOURCE).lower()

    # Check TuShare availability (if selected)
    if src == "tushare" and "tushare" not in _SOURCE_REGISTRY:
        raise DataSourceError(
            "TuShare data source not enabled. Please initialize and register TuShare first with `yquoter.init_tushare(token)`, "
            "or use source='spider' instead."
        )

    # Validate selected data source
    if src not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {src}; available sources: {list(_SOURCE_REGISTRY)}")

    logger.info(f"Using data source: {src}.")

    func_type = "realtime"
    if func_type not in _SOURCE_REGISTRY[src]:
        raise DataSourceError(f"Data source '{src}' does not support '{func_type}' data.")
    func = _SOURCE_REGISTRY[src][func_type]

    all_results = []

    # -------------------------------------------------------------
    # Core Logic: Dynamic Batching Strategy based on source
    # -------------------------------------------------------------
    if src == "tushare":
        # Tushare requires single-code calls; iterating manually.
        logger.info(f"Tushare source selected. Iterating through {len(code)} codes individually.")

        for code in code:
            # Parameters tailored for the single-code Tushare function (expecting 'code')
            params = {
                "market": market,
                "code": code,
                "fields": fields,
                **kwargs,
            }

            sig = inspect.signature(func)
            filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

            try:
                # Call the single-stock fetch function
                df = func(**filtered_params)

                if df is not None and not df.empty:
                    all_results.append(df)
                else:
                    logger.warning(f"Source '{src}' returned empty data for code: {code}.")

            except Exception as e:
                # Log the error and continue to the next code to maximize data retrieval
                logger.error(f"Failed to fetch data for code '{code}' from Tushare: {e}", exc_info=True)
                continue

    else:
        # Other data sources are assumed to support batch queries.
        logger.info(f"Source '{src}' is batch-compatible; making a single API call.")

        # Parameters for the batch query function (expecting 'codes')
        params = {
            "market": market,
            "code": code,  # Pass the full list of codes
            "fields": fields,
            **kwargs,
        }

        sig = inspect.signature(func)
        filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

        try:
            # Fetch data in a single batch
            df = func(**filtered_params)

            if df is not None and not df.empty:
                all_results.append(df)
            else:
                logger.warning(f"Batch query to source '{src}' returned empty data.")

        except Exception as e:
            # Batch query failure is considered critical for this source
            logger.error(f"Failed to fetch data from source '{src}' via batch query: {e}", exc_info=True)
            raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    if not all_results:
        # If all attempts failed or returned empty data
        logger.warning(f"All fetch attempts for market '{market}' failed or returned empty data.")
        # Return an empty DataFrame
        return pd.DataFrame()

    # 3. Concatenate and validate/order the final result
    final_df = pd.concat(all_results, ignore_index=True)

    return final_df

def _get_stock_financials(
        market: str,
        code: str,
        end_day: str,
        report_type: str = "CWBB",
        limit: int = 12,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """Unified interface for fetching stock financial statements.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code to fetch.
        end_day: Latest report period end date in ``YYYYMMDD`` format.
        report_type: Type of financial report. Options: 'CWBB'
            (Consolidated), 'LRB' (Income), 'ZCFZB' (Balance Sheet),
            'XJLLB' (Cash Flow), 'YJBB' (Earnings). Default is 'CWBB'.
        limit: Maximum number of recent reporting periods to fetch.
            Default is 12.
        source: Data source to use (e.g., 'tushare', 'spider').
        **kwargs: Additional keyword arguments for the source function.

    Returns:
        pd.DataFrame: Standardized financial statement data.

    Raises:
        DataSourceError: If the source is unknown or does not support
            'financials'.
        DataFetchError: If data fetching fails.
    """
    market = market.lower()
    end_day = parse_date_str(end_day)

    logger.info(f"Initiating financial data fetch for {market} of {code}.")

    src = (source or _DEFAULT_SOURCE).lower()

    # 1. Source availability check (TuShare specific check)
    if src == "tushare" and "tushare" not in _SOURCE_REGISTRY:
        raise DataSourceError(
            "TuShare data source not enabled. Please initialize and register TuShare first with `yquoter.init_tushare(token)`, "
            "or use source='spider' instead."
        )

    # 2. Validate selected data source
    if src not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {src}; available sources: {list(_SOURCE_REGISTRY)}")

    logger.info(f"Using data source: {src}.")

    # 3. Determine function type and validate source support
    func_type = "financials"
    if func_type not in _SOURCE_REGISTRY[src]:
        raise DataSourceError(f"Data source '{src}' does not support '{func_type}' data.")
    func = _SOURCE_REGISTRY[src][func_type]

    # 4. Construct unified parameters
    params = {
        "market": market,
        "code": code,
        "end_day": end_day,
        "report_type": report_type,
        "limit": limit,
        **kwargs,
    }

    # 5. Filter out parameters not supported by the target function using inspect
    sig = inspect.signature(func)
    filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

    try:
        # 6. Fetch data and return
        logger.info(f"Calling data source function with parameters: market={market}, code={code}, report_type={report_type}")
        df = func(**filtered_params)

    except Exception as e:
        logger.error(f"Failed to fetch data from source '{src}': {e}")
        raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    # Validation or standardization (omitted here, assumed to be in internal functions)
    return df


def _get_stock_profile(
        market: str,
        code: str,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """Unified interface for fetching company profile information.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code to fetch.
        source: Data source to use (e.g., 'tushare', 'spider').
        **kwargs: Additional keyword arguments for the source function.

    Returns:
        pd.DataFrame: Standardized company profile data (industry,
            main business, listing date, etc.).

    Raises:
        DataSourceError: If the source is unknown or does not support
            'profile'.
        DataFetchError: If data fetching fails.
    """
    market = market.lower()

    logger.info(f"Initiating profile data fetch for {market} of {code}.")

    src = (source or _DEFAULT_SOURCE).lower()

    # 1. Source availability check (TuShare specific check)
    if src == "tushare" and "tushare" not in _SOURCE_REGISTRY:
        raise DataSourceError(
            "TuShare data source not enabled. Please initialize and register TuShare first with `yquoter.init_tushare(token)`, "
            "or use source='spider' instead."
        )

    # 2. Validate selected data source
    if src not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {src}; available sources: {list(_SOURCE_REGISTRY)}")

    logger.info(f"Using data source: {src}.")

    # 3. Determine function type and validate source support (CORRECTED FUNC_TYPE)
    func_type = "profile"
    if func_type not in _SOURCE_REGISTRY[src]:
        raise DataSourceError(f"Data source '{src}' does not support '{func_type}' data.")
    func = _SOURCE_REGISTRY[src][func_type]

    # 4. Construct unified parameters
    params = {
        "market": market,
        "code": code,
        **kwargs,
    }

    # 5. Filter out parameters not supported by the target function
    sig = inspect.signature(func)
    filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

    try:
        # 6. Fetch data and return
        logger.info(
            f"Calling data source function with parameters: market={market}, code={code}")
        df = func(**filtered_params)

    except Exception as e:
        logger.error(f"Failed to fetch data from source '{src}': {e}")
        raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    return df


# ======================================================================
# Async wrappers (internal, for use in reporting.py async kernel)
# ======================================================================


async def _aget_stock_history(
    market: str,
    code: str,
    start: str = None,
    end: str = None,
    klt: int = 101,
    fqt: int = 1,
) -> pd.DataFrame:
    """Async version: directly awaits the async spider implementation.

    Bypasses cache. Use the sync ``_get_stock_history`` when caching
    is desired.
    """
    from yquoter.spider_source import async_get_stock_history_spider
    from yquoter.config import FREQ_TO_KLT

    if start is None and end is None:
        start = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        end = datetime.now().strftime('%Y%m%d')
    elif start is None:
        end = parse_date_str(end)
        start = (datetime.strptime(end, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
    elif end is None:
        start = parse_date_str(start)
        end = datetime.now().strftime('%Y%m%d')

    start = parse_date_str(start)
    end = parse_date_str(end)

    if isinstance(klt, str):
        klt = klt.lower()
        if klt not in FREQ_TO_KLT:
            raise ParameterError(f"Unknown frequency: {klt}")
        klt = FREQ_TO_KLT[klt]

    return await async_get_stock_history_spider(
        market=market, code=code, start=start, end=end, klt=klt, fqt=fqt
    )


async def _aget_stock_realtime(
        market: str,
        code: str,
        fields: list[str] = None,
) -> pd.DataFrame:
    """Async version: fetch real-time quotes without thread pool."""
    from yquoter.spider_source import async_get_stock_realtime_spider
    return await async_get_stock_realtime_spider(
        market=market, code=code, fields=fields
    )


async def _aget_stock_profile(
        market: str,
        code: str,
) -> pd.DataFrame:
    """Async version: fetch company profile without thread pool."""
    from yquoter.spider_source import async_get_stock_profile_spider
    return await async_get_stock_profile_spider(market=market, code=code)


async def _aget_stock_factors(
        market: str,
        code: str,
        trade_date: str,
) -> pd.DataFrame:
    """Async version: fetch factors without thread pool."""
    from yquoter.spider_source import async_get_stock_factors_spider
    return await async_get_stock_factors_spider(
        market=market, code=code, trade_date=trade_date
    )


def _get_stock_factors(
        market: str,
        code: str,
        trade_date: str,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """Unified interface for fetching stock fundamental factors.

    Fetches valuation and market factors such as PE, PB, and market
    capitalization for a specific date.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code to fetch.
        trade_date: Date for the factor snapshot in ``YYYYMMDD`` format.
        source: Data source to use (e.g., 'tushare', 'spider').
        **kwargs: Additional keyword arguments for the source function.

    Returns:
        pd.DataFrame: Standardized factor data.

    Raises:
        DataSourceError: If the source is unknown or does not support
            'factors'.
        DataFetchError: If data fetching fails.
    """
    market = market.lower()
    trade_date = parse_date_str(trade_date)

    logger.info(f"Initiating factors data fetch for {market} of {code}.")

    src = (source or _DEFAULT_SOURCE).lower()

    # 1. Source availability check (TuShare specific check)
    if src == "tushare" and "tushare" not in _SOURCE_REGISTRY:
        raise DataSourceError(
            "TuShare data source not enabled. Please initialize and register TuShare first with `yquoter.init_tushare(token)`, "
            "or use source='spider' instead."
        )

    # 2. Validate selected data source
    if src not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {src}; available sources: {list(_SOURCE_REGISTRY)}")

    logger.info(f"Using data source: {src}.")

    # 3. Determine function type and validate source support (CORRECTED FUNC_TYPE)
    func_type = "factors"
    if func_type not in _SOURCE_REGISTRY[src]:
        raise DataSourceError(f"Data source '{src}' does not support '{func_type}' data.")
    func = _SOURCE_REGISTRY[src][func_type]

    # 4. Construct unified parameters
    params = {
        "market": market,
        "code": code,
        "trade_date": trade_date,
        **kwargs,
    }

    # 5. Filter out parameters not supported by the target function
    sig = inspect.signature(func)
    filtered_params = {k: v for k, v in params.items() if k in sig.parameters}

    try:
        # 6. Fetch data and return
        logger.info(f"Calling data source function with parameters: market={market}, code={code}, trade_date={trade_date}")
        df = func(**filtered_params)

    except Exception as e:
        logger.error(f"Failed to fetch data from source '{src}': {e}")
        raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    return df