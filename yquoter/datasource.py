import inspect
import pandas as pd
from datetime import datetime
from typing import Dict, Callable, Optional, Union, List
from yquoter.cache import get_cache_path, cache_exists, load_cache, save_cache
from yquoter.spider_source import get_stock_history_spider, get_stock_realtime_spider
from yquoter.utils import *
from yquoter.exceptions import DataSourceError, ParameterError, DataFetchError, DataFormatError
from yquoter.logger import get_logger
from yquoter.config import modify_df_path

# Global registry for data sources
_SOURCE_REGISTRY: Dict[str, Callable] = {
    "spider": get_stock_history_spider
}
_DEFAULT_SOURCE = "spider"  # Spider source takes priority
logger = get_logger(__name__)

# Standardized columns for History-DataFrame format
_REQUIRED_COLUMNS_BASIC = ["date", "open", "high", "low", "close", "volume", "amount"]
_REQUIRED_COLUMNS_FULL = ["date", "open", "high", "low", "close", "volume", "amount", "change%", "turnover%", "change", "amplitude%"]
def _validate_dataframe(df: pd.DataFrame, fields: str) -> pd.DataFrame:
    """
    Validate DataFrame structure against required columns

        Args:
            df: DataFrame to validate
            fields: Validation mode ('basic' or 'full')

        Returns:
            Validated DataFrame (filtered to required columns)

        Raises:
            DataFormatError: If DataFrame is empty or missing required columns
    """

    if df is None or df.empty:
        raise DataFormatError("Data source returned empty data or parsing failed; validation cannot proceed.")
    missing = None
    _REQUIRED_COLUMNS = None
    if fields == "full":
        missing = [col for col in _REQUIRED_COLUMNS_FULL if col not in df.columns]
        _REQUIRED_COLUMNS = _REQUIRED_COLUMNS_FULL
    elif fields == "basic":
        missing = [col for col in _REQUIRED_COLUMNS_BASIC if col not in df.columns]
        _REQUIRED_COLUMNS = _REQUIRED_COLUMNS_BASIC
    if missing:
        raise DataFormatError(f"Data source returned invalid format: Missing columns {missing}; required columns are {_REQUIRED_COLUMNS}")
    df = df[_REQUIRED_COLUMNS]
    if fields == "full":
        print("Warning: Direct print in 'full' mode may cause output truncation; adjust with pd.set_option")
    return df


# Frequency to klt (k-line type) mapping
FREQ_TO_KLT = {
    ## Daily/Weekly/Monthly
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


def register_source(name: str, func: Callable = None):
    """
    Register a new data source (supports functional call and decorator usage)

        Args:
            name: Unique name of the data source (case-insensitive)
            func: Data fetch function to register (optional for decorator use)

        Returns:
            Decorator if func is None, otherwise the registered function
    """

    def decorator(f: Callable):
        _SOURCE_REGISTRY[name.lower()] = f
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

    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    delta_days = (end_dt - start_dt).days

    # Smart warning for short time ranges
    if freq in ("w", "weekly") and delta_days < 7:
        print("⚠️ Time range too short; weekly K-line data may be unavailable")
    elif freq in ("m", "monthly") and delta_days < 28:
        print("⚠️ Time range too short; monthly K-line data may be unavailable")

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

    # Override klt with freq if freq is provided
    if freq:
        freq = freq.lower()
        if freq not in FREQ_TO_KLT:
            raise ParameterError(f"Unknown frequency: {freq}; available values: {list(FREQ_TO_KLT)}")
        klt = FREQ_TO_KLT[freq]

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
    func = _SOURCE_REGISTRY[src]

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
        df = func(**filtered_params)

    except Exception as e:
        logger.error(f"Failed to fetch data from source '{src}': {e}")
        raise DataFetchError(f"Failed to fetch data from source '{src}'") from e

    # 3. Save to cache if data is valid
    if df is not None and not df.empty:
        save_cache(cache_path, df)  # CacheSaveError thrown if save fails
        modify_df_path(cache_path)

    # 4. Validate and return data
    return _validate_dataframe(df, fields)


def get_stock_realtime(
        market: str,
        code: str,
        start: str,
        end: str,
        source: Optional[str] = None,
        freq: Optional[str] = None,
        klt: int = 101,
        fqt: int = 1,
        **kwargs
) -> pd.DataFrame:
    pass  # TODO:spider & tushare

