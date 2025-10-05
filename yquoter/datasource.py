import inspect
import pandas as pd
from datetime import datetime
from typing import Dict, Callable, Optional, Union, List
from yquoter.cache import get_cache_path, cache_exists, load_cache, save_cache
from yquoter.spider_source import get_stock_history_spider, get_stock_realtime_spider, get_stock_financials_spider, get_stock_profile_spider, get_stock_factors_spider
from yquoter.utils import *
from yquoter.exceptions import DataSourceError, ParameterError, DataFetchError, DataFormatError
from yquoter.logger import get_logger
from yquoter.config import modify_df_path
from yquoter.utils import _validate_dataframe

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


# Frequency to klt (k-line type) mapping
FREQ_TO_KLT = {
    # Daily/Weekly/Monthly
    "daily": 1, "day": 1, "d": 1,
    "weekly": 2, "week": 2, "w": 2,
    "monthly": 3, "month": 3, "m": 3,

    # Minute levels
    "1min": 101, "1m": 101,
    "5min": 102, "5m": 102,
    "15min": 103, "15m": 103,
    "30min": 104, "30m": 104,
    "60min": 105, "60m": 105, "1h": 105,
}


def register_source(source_name: str, func_type: str, func: Callable = None):
    """
    Register a specific function type (e.g., 'realtime') for a data source (e.g., 'tushare').

        Args:
            source_name: Unique name of the data source (case-insensitive).
            func_type: The type of data being fetched (e.g., 'history', 'realtime', 'financials').
            func: Data fetch function to register (optional for decorator use).

        Returns:
            Decorator if func is None, otherwise the registered function.
    """
    source_name = source_name.lower()
    func_type = func_type.lower()

    def decorator(f: Callable):
        if source_name not in _SOURCE_REGISTRY:
            _SOURCE_REGISTRY[source_name] = {}
        _SOURCE_REGISTRY[source_name][func_type] = f
        logger.info(f"Source '{source_name}' registered for function type '{func_type}'")
        return f

    if func is not None:  # Regular function call
        return decorator(func)

    return decorator  # Decorator usage


def set_default_source(name: str) -> None:
    """
    Set global default data source

        Args:
            name: Name of the data source to set as default (case-insensitive)

        Raises:
            DataSourceError: If the specified data source is not registered
    """
    global _DEFAULT_SOURCE
    name = name.lower()
    if name not in _SOURCE_REGISTRY:
        raise DataSourceError(f"Unknown data source: {name}; available sources: {list(_SOURCE_REGISTRY)}")
    _DEFAULT_SOURCE = name
    logger.info(f"Default data source set to: {name}")


def get_stock_history(
    market: str,
    code: str,
    start: str,
    end: str,
    source: Optional[str] = None,
    freq: Optional[str] = None,
    klt: int = 101,
    fqt: int = 1,
    fields: str = "basic",
    **kwargs
) -> pd.DataFrame:
    """
    Unified interface for fetching stock historical data

        Args:
            market: Market identifier ('cn' for China, 'hk' for Hong Kong, 'us' for US)
            code: Stock code
            start: Start date (supports YYYY-MM-DD format, auto-parsed)
            end: End date (supports YYYY-MM-DD format, auto-parsed)
            source: Data source to use (defaults to global default: 'spider')
            freq: Data frequency (e.g., 'daily', '1min'; overrides klt if provided)
            klt: K-line type code (1=daily, 2=weekly, 101=1min; default: 101)
            fqt: Forward/factor adjustment type (default: 1)
            fields: Data field set ('basic' or 'full'; default: 'basic')
            **kwargs: Additional parameters passed to the data source function

        Returns:
            Validated DataFrame containing stock historical data

        Raises:
            DataSourceError: Invalid/missing data source or uninitialized TuShare
            ParameterError: Invalid frequency parameter
            DataFetchError: Failed to fetch data from the source
            DataFormatError: Invalid data format returned by source
            DateFormatError: Invalid date format (thrown by parse_date_str)
    """
    market = market.lower()
    # Parse date strings (DateFormatError thrown if format is invalid)
    start = parse_date_str(start)
    end = parse_date_str(end)
    logger.info(f"Fetching data for {market}:{code} from {start} to {end}")
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    delta_days = (end_dt - start_dt).days

    # Smart warning for short time ranges
    if freq in ("w", "weekly") and delta_days < 7:
        print("⚠️ Time range too short; weekly K-line data may be unavailable")
    elif freq in ("m", "monthly") and delta_days < 28:
        print("⚠️ Time range too short; monthly K-line data may be unavailable")

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
    if freq:
        freq = freq.lower()
        if freq not in FREQ_TO_KLT:
            raise ParameterError(f"Unknown frequency: {freq}; available values: {list(FREQ_TO_KLT)}")
        klt = FREQ_TO_KLT[freq]
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
        "freq": freq,
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


def get_stock_realtime(
        market: str,
        codes: Union[str, list[str]] = [],
        fields: Union[str, list[str]] = [],
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """
    Unified interface to fetch real-time stock quotes from various data sources.

    Args:
        market: Market identifier (e.g., 'cn', 'hk', 'us').
        codes: Stock code(s) to fetch. Can be a single string or a list.
        fields: Optional list of standardized fields to filter the results.
        source: Specific data source to use (e.g., 'tushare', 'spider').
        **kwargs: Additional keyword arguments passed to the underlying source function.

    Returns:
        DataFrame with standardized real-time quotes.

    Raises:
        DataSourceError: If the specified source is unknown or not initialized.
        DataFetchError: If the data fetching operation fails at the source level.
    """

    market = market.lower()

    # 1. Standardize codes and fields to lists
    if isinstance(codes, str):
        codes = [codes]
    if isinstance(fields, str):
        fields = [fields]

    logger.info(f"Initiating real-time data fetch for {market} with {len(codes)} code(s).")

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
        logger.info(f"Tushare source selected. Iterating through {len(codes)} codes individually.")

        for code in codes:
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
            "codes": codes,  # Pass the full list of codes
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
        # Return an empty DataFrame with correct columns
        return _validate_dataframe(pd.DataFrame(), fields)

    # 3. Concatenate and validate/order the final result
    final_df = pd.concat(all_results, ignore_index=True)

    return _validate_dataframe(final_df, fields)

def get_stock_financials(
        market: str,
        code: str,
        period: str
):
    pass  # TODO!

def get_stock_profile(
        market: str,
        code: str,
):
    pass  # TODO!

def get_stock_factors(
        market: str,
        code: str,
        trade_date: str
):
    pass  # TODO!