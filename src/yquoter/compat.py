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
    """Decorator to mark functions as deprecated with an alternative API recommendation.

    Args:
        new_api: Replacement API path (e.g., ``'Stock.get_history()'``).
        version: Version when the deprecation occurred. Default is
            ``'0.3.0'``.

    Returns:
        Callable: Decorated function that emits a ``DeprecationWarning``
        on invocation.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_history()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        klt: K-line type. Default is 101.
        fqt: Forward-adjusted type. Default is 1.
        fields: Data fields to return. Default is ``"basic"``.
        source: Optional data source override.

    Returns:
        pd.DataFrame: Historical stock data.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_realtime()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol or list of symbols.
        fields: Data fields to retrieve.
        source: Optional data source override.

    Returns:
        pd.DataFrame: Real-time market data.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_profile()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        source: Optional data source override.

    Returns:
        pd.DataFrame: Company profile data.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_factors()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        trade_date: Specific trading date in ``YYYY-MM-DD`` format.
        source: Optional data source override.

    Returns:
        pd.DataFrame: Factor metrics.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_financials()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        end_day: Report end date in ``YYYY-MM-DD`` format.
        report_type: Financial report type. Default is ``'CWBB'``.
        limit: Number of periods to retrieve. Default is 12.
        source: Optional data source override.

    Returns:
        pd.DataFrame: Financial data.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_ma()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: MA calculation results.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_boll()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: Bollinger Band calculation results.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_vol_ratio()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: Volume ratio calculation results.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_max_drawdown()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: Max drawdown calculation results.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_rsi()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: RSI calculation results.
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

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_rv()` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        n: Period length.
        df: Input DataFrame (alternative to ``market``/``code``).

    Returns:
        pd.DataFrame: Volatility calculation results.
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
        output_dir: Optional[str] = None,
        llm_provider: Optional[str] = None,
) -> str:
    """DEPRECATED: Generate stock analysis report.

    .. deprecated:: 0.3.0
       Use :meth:`Stock.get_report(llm_provider=...)` instead.

    Args:
        market: Exchange market code.
        code: Stock symbol.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        source: Optional data source override.
        language: Report language. Default is ``'en'``.
        output_dir: Custom output directory.
        llm_provider: Optional LLM provider for AI analysis.
            ``None`` (default) skips AI. Accepts names like
            ``"deepseek"``, ``"ChatGPT"``, ``"Claude"``.

    Returns:
        str: Generated report content in Markdown format.
    """
    return _generate_stock_report(
        market, code, start, end, source, language, output_dir,
        llm_provider=llm_provider,
    )