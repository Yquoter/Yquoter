# yquoter/compat.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

from yquoter.datasource import (
    _get_stock_history,
    _get_stock_realtime,
    _get_stock_financials,
    _get_stock_profile,
    _get_stock_factors,
)
from yquoter.indicators import (
    _get_ma_n,
    _get_rv_n,
    _get_rsi_n,
    _get_boll_n,
    _get_vol_ratio,
    _get_max_drawdown
)
from yquoter.reporting import _generate_stock_report
import warnings
import pandas as pd
from functools import wraps
from typing import Callable, Any, Union, Optional, TypeVar

# Type variable for generic function typing
F = TypeVar('F', bound=Callable[..., Any])


def deprecated(new_api: str, version: str = "0.3.0") -> Callable[[F], F]:
    """Mark functions as deprecated with alternative API recommendation.

    Args:
        new_api: Replacement API path (e.g. 'module.new_function')
        version: Version when deprecation occurred (default: '0.3.0')

    Returns:
        Decorated function that emits deprecation warning on invocation.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def new_func(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(
                f"Function '{func.__module__}.{func.__qualname__}' is deprecated "
                f"since version {version}. Please use '{new_api}' instead.",
                category=DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)

        return new_func  # type: ignore

    return decorator


@deprecated(new_api="Stock.get_history()", version="0.3.0")
def get_stock_history(
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
    """DEPRECATED: Get historical stock data.

    Warning: Use Stock.get_history() instead.

    Args:
        market: Exchange market code
        code: Stock symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        klt: K-line type (default: 101)
        fqt: Forward-adjusted type (default: 1)
        fields: Data fields to return (default: "basic")
        source: Optional data source override

    Returns:
        DataFrame containing historical stock data
    """
    return _get_stock_history(market, code, start, end, klt, fqt, fields, source, **kwargs)


@deprecated(new_api="Stock.get_realtime()", version="0.3.0")
def get_stock_realtime(
        market: str,
        code: Union[str, list[str]],
        fields: Union[str, list[str]] = None,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """DEPRECATED: Get real-time stock quotes.

    Warning: Use Stock.get_realtime() instead.

    Args:
        market: Exchange market code
        code: Stock symbol or list of symbols
        fields: Data fields to retrieve
        source: Optional data source override

    Returns:
        DataFrame with real-time market data
    """
    return _get_stock_realtime(market, code, fields, source, **kwargs)


@deprecated(new_api="Stock.get_profile()", version="0.3.0")
def get_stock_profile(
        market: str,
        code: str,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """DEPRECATED: Get company profile information.

    Warning: Use Stock.get_profile() instead.

    Args:
        market: Exchange market code
        code: Stock symbol
        source: Optional data source override

    Returns:
        DataFrame containing company profile data
    """
    return _get_stock_profile(market, code, source, **kwargs)


@deprecated(new_api="Stock.get_factors()", version="0.3.0")
def get_stock_factors(
        market: str,
        code: str,
        trade_date: str,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """DEPRECATED: Get stock factor data.

    Warning: Use Stock.get_factors() instead.

    Args:
        market: Exchange market code
        code: Stock symbol
        trade_date: Specific trading date (YYYY-MM-DD)
        source: Optional data source override

    Returns:
        DataFrame with factor metrics
    """
    return _get_stock_factors(market, code, trade_date, source, **kwargs)


@deprecated(new_api="Stock.get_financials()", version="0.3.0")
def get_stock_financials(
        market: str,
        code: str,
        end_day: str,
        report_type: str = 'CWBB',
        limit: int = 12,
        source: Optional[str] = None,
        **kwargs
) -> pd.DataFrame:
    """DEPRECATED: Get financial statements.

    Warning: Use Stock.get_financials() instead.

    Args:
        market: Exchange market code
        code: Stock symbol
        end_day: Report end date (YYYY-MM-DD)
        report_type: Financial report type (default: 'CWBB')
        limit: Number of periods to retrieve (default: 12)
        source: Optional data source override

    Returns:
        DataFrame containing financial data
    """
    return _get_stock_financials(market, code, end_day, report_type, limit, source, **kwargs)


@deprecated(new_api="Stock.get_ma()", version="0.3.0")
def get_ma_n(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate moving average.

    Warning: Use Stock.get_ma() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with MA calculations
    """
    return _get_ma_n(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_boll()", version="0.3.0")
def get_boll_n(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate Bollinger Bands.

    Warning: Use Stock.get_boll() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with Bollinger Band calculations
    """
    return _get_boll_n(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_vol_ratio()", version="0.3.0")
def get_vol_ratio(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate volume ratio.

    Warning: Use Stock.get_vol_ratio() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with volume ratio calculations
    """
    return _get_vol_ratio(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_max_drawdown()", version="0.3.0")
def get_max_drawdown(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate maximum drawdown.

    Warning: Use Stock.get_max_drawdown() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with max drawdown calculations
    """
    return _get_max_drawdown(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_rsi()", version="0.3.0")
def get_rsi_n(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate Relative Strength Index.

    Warning: Use Stock.get_rsi() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with RSI calculations
    """
    return _get_rsi_n(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_rv()", version="0.3.0")
def get_rv_n(
        market: str = None,
        code: str = None,
        start: str = None,
        end: str = None,
        n: int = None,
        df: pd.DataFrame = None
) -> pd.DataFrame:
    """DEPRECATED: Calculate realized volatility.

    Warning: Use Stock.get_rv() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        n: Period length (optional)
        df: Input DataFrame (alternative to market/code)

    Returns:
        DataFrame with volatility calculations
    """
    return _get_rv_n(market, code, start, end, n, df)


@deprecated(new_api="Stock.get_report()", version="0.3.0")
def generate_stock_report(
        market: str = None,
        code: str = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: Optional[str] = None,
        language: str = 'en',
        output_dir: Optional[str] = None
) -> str:
    """DEPRECATED: Generate stock analysis report.

    Warning: Use Stock.get_report() instead.

    Args:
        market: Exchange market code (optional)
        code: Stock symbol (optional)
        start: Start date (YYYY-MM-DD, optional)
        end: End date (YYYY-MM-DD, optional)
        source: Optional data source override
        language: Report language (default: 'en')
        output_dir: Custom output directory (optional)

    Returns:
        Path to generated report file
    """
    return _generate_stock_report(market, code, start, end, source, language, output_dir)