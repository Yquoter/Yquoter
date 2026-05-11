# yquoter/datasource.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unified data source interface, registry, and dispatch layer.

Yquoter's data source plugin system.  All data retrieval flows through
this module, which handles source resolution, caching, and result
validation before dispatching to the appropriate
:class:`~yquoter.plugin_base.DataSource` implementation.
"""

import inspect
from typing import Any, Dict, Callable, Optional, Union

import pandas as pd

from datetime import datetime, timedelta

from yquoter.cache import (
    cache_get, cache_set,
    make_cache_key,
    get_cache_path, cache_exists, load_cache, save_cache,
)
from yquoter.exceptions import (
    DataSourceError,
    ParameterError,
    DataFetchError,
)
from yquoter.logger import get_logger
from yquoter.config import modify_df_path
from yquoter.utils import _validate_dataframe, parse_date_str
from yquoter.plugin_base import DataSource

logger = get_logger(__name__)


# ======================================================================
# Plugin registry
# ======================================================================

#: Global registry mapping source names to DataSource instances.
_SOURCE_REGISTRY: Dict[str, DataSource] = {}

#: Default source used when none is explicitly specified.
_DEFAULT_SOURCE = "spider"

#: Names that are recognised but require explicit initialisation before use.
#: Maps name -> user-facing hint string.
_UNAVAILABLE_SOURCES: Dict[str, str] = {
    "tushare": (
        "Use yquoter.init_tushare(token) to enable the Tushare data source."
    ),
}


def _register_builtin_sources() -> None:
    """Register all built-in data source plugins."""
    from yquoter.spider_source import SpiderDataSource

    spider = SpiderDataSource()
    _SOURCE_REGISTRY[spider.name] = spider


_register_builtin_sources()


def discover_plugins() -> None:
    """Auto-discover third-party DataSource plugins via entry_points.

    Scans the ``yquoter.data_sources`` entry point group and registers
    any plugin whose name does not already exist in the registry.
    Third-party packages declare their plugin in ``pyproject.toml``::

        [project.entry-points."yquoter.data_sources"]
        akshare = "my_package:AkShareDataSource"
    """
    from importlib.metadata import entry_points

    eps = entry_points(group="yquoter.data_sources")
    discovered = 0
    for ep in eps:
        if ep.name not in _SOURCE_REGISTRY:
            try:
                cls = ep.load()
                instance = cls()
                _SOURCE_REGISTRY[ep.name] = instance
                discovered += 1
                logger.info("Discovered data source plugin: %s", ep.name)
            except Exception as e:
                logger.warning(
                    "Failed to load plugin '%s': %s", ep.name, e,
                )
    if discovered:
        logger.info("Plugin discovery complete: %d new source(s)", discovered)


# ======================================================================
# DynamicDataSource  (backward-compatibility adapter)
# ======================================================================


class DynamicDataSource(DataSource):
    """Adapter that wraps legacy ``register_source()`` callables as a DataSource.

    This preserves backward compatibility for any code that uses the old
    ``register_source(name, type, func)`` API.  The class stores per-type
    callables and dispatches to them using the original ``inspect.signature``
    parameter filtering.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._functions: Dict[str, Callable] = {}

    # -- identity -----------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_types(self) -> set:
        return set(self._functions.keys())

    # -- registration -------------------------------------------------------------

    def set_function(
        self,
        func_type: str,
        func: Callable,
        overwrite_callback: Optional[Callable[[str, str, str, str], bool]] = None,
    ) -> None:
        """Register a function for *func_type*, optionally prompting on conflict.

        Args:
            func_type: Type name (e.g. ``"history"``, ``"realtime"``).
            func: The callable to register.
            overwrite_callback: ``(source_name, func_type, old_name, new_name)
                -> bool``.  Return ``True`` to allow overwrite.
        """
        if overwrite_callback and func_type in self._functions:
            old = self._functions[func_type].__name__
            new = func.__name__
            if not overwrite_callback(self._name, func_type, old, new):
                logger.info(
                    "Overwrite rejected for '%s' type '%s' (retaining %s)",
                    self._name, func_type, old,
                )
                return
        self._functions[func_type] = func
        logger.info(
            "Dynamic source '%s' registered for type '%s': %s",
            self._name, func_type, func.__name__,
        )

    # -- dispatch helpers ---------------------------------------------------------

    @staticmethod
    def _call_with_filter(func: Callable, **kwargs) -> Any:
        """Call *func* passing only the keyword arguments it accepts."""
        sig = inspect.signature(func)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return func(**filtered)

    def _dispatch(self, func_type: str, **kwargs) -> pd.DataFrame:
        if func_type not in self._functions:
            raise DataSourceError(
                f"Dynamic source '{self._name}' does not have a '{func_type}' "
                f"function registered."
            )
        return self._call_with_filter(self._functions[func_type], **kwargs)

    # -- DataSource methods -------------------------------------------------------

    def get_history(self, market, code, start, end, klt=101, fqt=1, fields="basic", **kwargs) -> pd.DataFrame:
        return self._dispatch(
            "history",
            market=market, code=code, start=start, end=end,
            klt=klt, fqt=fqt, fields=fields, **kwargs,
        )

    def get_realtime(self, market, code, fields=None, **kwargs) -> pd.DataFrame:
        return self._dispatch(
            "realtime", market=market, code=code, fields=fields, **kwargs,
        )

    def get_financials(self, market, code, end_day, report_type="CWBB",
                       limit=12, **kwargs) -> pd.DataFrame:
        return self._dispatch(
            "financials",
            market=market, code=code, end_day=end_day,
            report_type=report_type, limit=limit, **kwargs,
        )

    def get_profile(self, market, code, **kwargs) -> pd.DataFrame:
        return self._dispatch("profile", market=market, code=code, **kwargs)

    def get_factors(self, market, code, trade_date, **kwargs) -> pd.DataFrame:
        return self._dispatch(
            "factors", market=market, code=code, trade_date=trade_date, **kwargs,
        )


# ======================================================================
# Source resolution helpers
# ======================================================================


def _resolve_source(
    source: Optional[Union[str, DataSource]] = None,
) -> DataSource:
    """Resolve a source identifier to a :class:`DataSource` instance.

    Accepts:

    * ``None`` -- returns the default source.
    * ``str`` -- looks up the name in ``_SOURCE_REGISTRY``.
    * :class:`DataSource` -- returned as-is.

    Args:
        source: Source identifier.

    Returns:
        A DataSource instance ready for use.

    Raises:
        DataSourceError: If the source name is unknown or unavailable.
    """
    if source is None:
        source = _DEFAULT_SOURCE

    if isinstance(source, DataSource):
        return source

    if isinstance(source, str):
        name = source.lower()
        if name in _SOURCE_REGISTRY:
            return _SOURCE_REGISTRY[name]

        avail = sorted(_SOURCE_REGISTRY.keys())
        msg = f"Unknown data source: '{source}'; available sources: {avail}."
        if name in _UNAVAILABLE_SOURCES:
            msg += f" {_UNAVAILABLE_SOURCES[name]}"
        raise DataSourceError(msg)

    raise DataSourceError(f"Invalid source type: {type(source).__name__}")


# ======================================================================
# Public API: register / set-default
# ======================================================================


def _overwrite_prompt(source_name, func_type, old_name, new_name) -> bool:
    """Prompt the user to confirm overwriting an existing function."""
    from yquoter.utils import _is_interactive_session

    if not _is_interactive_session():
        logger.warning(
            "Non-interactive session; rejecting overwrite of '%s' type '%s' "
            "(old: %s, new: %s)",
            source_name, func_type, old_name, new_name,
        )
        return False

    try:
        answer = input(
            f"Overwrite source '{source_name}' function type "
            f"'{func_type}'? [y/N]: "
        ).lower()
        return answer == "y"
    except EOFError:
        logger.warning("EOF reading input; overwrite rejected.")
        return False


def register_source(
    source_name: str,
    func_type_or_source: Union[str, DataSource] = None,
    func: Callable = None,
):
    """Register a data source or a single function for a source.

    Two calling conventions are supported:

    1. **DataSource instance** — register a complete DataSource::

           register_source("my_source", MyDataSource())

    2. **Decorator / callable** — register a single function type
       (legacy compat)::

           register_source("my_source", "history", my_history_func)

           @register_source("my_source", "realtime")
           def my_realtime(**kwargs): ...

    If *source_name* matches a built-in source (e.g. ``"spider"``),
    the registration is redirected to ``{source_name}_custom`` to
    avoid accidentally overriding built-in behaviour.

    Args:
        source_name: Data source name (e.g. ``"my_source"``).
        func_type_or_source: Either a ``DataSource`` instance to
            register directly, or a function type string
            (``"history"``, ``"realtime"``, etc.) when used with
            *func*.
        func: The callable, or ``None`` for decorator usage.  Only
            meaningful when *func_type_or_source* is a string.

    Returns:
        The registered callable or DataSource (or a decorator wrapper).
    """
    # -- Branch 1: DataSource instance registration -----------------------
    if isinstance(func_type_or_source, DataSource):
        if func is not None:
            raise ParameterError(
                "register_source accepts (name, DataSource) or "
                "(name, func_type, func), not both."
            )
        source_name = source_name.lower()
        instance = func_type_or_source

        if source_name in _SOURCE_REGISTRY and not isinstance(
            _SOURCE_REGISTRY[source_name], DynamicDataSource
        ):
            source_name = f"{source_name}_custom"
            logger.warning(
                "'%s' is a built-in source; registering as '%s' instead.",
                func_type_or_source.name, source_name,
            )

        _SOURCE_REGISTRY[source_name] = instance
        logger.info("Source '%s' registered (type=%s).", source_name, type(instance).__name__)
        return instance

    # -- Branch 2: function-type registration (legacy) --------------------
    source_name = source_name.lower()
    func_type = (func_type_or_source or "").lower()

    def decorator(f: Callable):
        actual_name = source_name

        # Redirect if the name clashes with a built-in DataSource.
        if source_name in _SOURCE_REGISTRY and not isinstance(
            _SOURCE_REGISTRY[source_name], DynamicDataSource
        ):
            actual_name = f"{source_name}_custom"
            logger.warning(
                "'%s' is a built-in source; registering as '%s' instead.",
                source_name, actual_name,
            )

        if actual_name not in _SOURCE_REGISTRY:
            _SOURCE_REGISTRY[actual_name] = DynamicDataSource(actual_name)
        elif not isinstance(_SOURCE_REGISTRY[actual_name], DynamicDataSource):
            # Safety net -- should not happen after the redirect above.
            raise DataSourceError(
                f"Cannot register functions for built-in source '{actual_name}'."
            )

        _SOURCE_REGISTRY[actual_name].set_function(
            func_type, f, overwrite_callback=_overwrite_prompt,
        )
        return f

    if func is not None:
        return decorator(func)
    return decorator


def _register_tushare_module() -> None:
    """Register the Tushare data source plugin.

    Called by :func:`yquoter.init_tushare` after token validation.
    """
    if "tushare" in _SOURCE_REGISTRY:
        logger.warning("Source 'tushare' is already registered.")
        return

    from yquoter.tushare_source import TushareDataSource

    _UNAVAILABLE_SOURCES.pop("tushare", None)
    _SOURCE_REGISTRY["tushare"] = TushareDataSource()
    logger.info("Source 'tushare' registered.")


def set_default_source(name: str) -> None:
    """Set the global default data source.

    Args:
        name: Source name (case-insensitive).

    Raises:
        DataSourceError: If the name is not registered.
    """
    global _DEFAULT_SOURCE
    name = name.lower()

    if name in _SOURCE_REGISTRY:
        _DEFAULT_SOURCE = name
        logger.info("Default data source set to: %s", name)
        return

    avail = sorted(_SOURCE_REGISTRY.keys())
    msg = f"Unknown data source: '{name}'; available: {avail}."
    if name in _UNAVAILABLE_SOURCES:
        msg += f" {_UNAVAILABLE_SOURCES[name]}"
    raise DataSourceError(msg)


# ======================================================================
# Synchronous dispatch functions  (public within the package)
# ======================================================================


def _get_stock_history(
    market: str,
    code: str,
    start: str = None,
    end: str = None,
    klt: Union[str, int] = 101,
    fqt: int = 1,
    fields: str = "basic",
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Fetch historical stock data with caching.

    Args:
        market: Market identifier (``"cn"``, ``"hk"``, ``"us"``).
        code: Stock ticker symbol.
        start: Start date.  Supports ``YYYY-MM-DD`` and similar.
        end: End date.
        klt: K-line type (101=daily, 102=weekly, 103=monthly).
        fqt: Forward-adjustment type (1=adjusted, 2=unadjusted).
        fields: ``"basic"`` or ``"full"`` column set.
        source: Data source name or instance.  Defaults to global default.
        **kwargs: Forwarded to the source implementation.

    Returns:
        DataFrame with historical OHLCV data.
    """
    from yquoter.config import FREQ_TO_KLT

    # -- date defaults --
    if start is None and end is None:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
    elif start is None and end is not None:
        end = parse_date_str(end)
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=30)).strftime(
            "%Y%m%d"
        )
    elif end is None and start is not None:
        start = parse_date_str(start)
        end = datetime.now().strftime("%Y%m%d")

    market = market.lower()
    start = parse_date_str(start)
    end = parse_date_str(end)
    logger.info("Fetching history for %s:%s from %s to %s", market, code, start, end)

    # -- source resolution --
    src = _resolve_source(source)

    if "history" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support history data."
        )

    # -- klt normalisation --
    if klt is not None:
        if isinstance(klt, str):
            klt = klt.lower()
            if klt not in FREQ_TO_KLT:
                raise ParameterError(
                    f"Unknown frequency: {klt}; available: {list(FREQ_TO_KLT)}"
                )
            klt = FREQ_TO_KLT[klt]

    # -- cache check (L1 -> L2) --
    cache_key = make_cache_key(
        "history", source=src.name, market=market, code=code,
        start=start, end=end, klt=str(klt), fqt=str(fqt),
    )
    cached = cache_get(cache_key, "history")
    if cached is not None:
        logger.info("Returning cached history for %s:%s", market, code)
        return _validate_dataframe(cached, fields)

    # -- fetch from source --
    logger.info("Cache miss; fetching history from '%s'", src.name)
    try:
        df = src.get_history(
            market=market, code=code, start=start, end=end,
            klt=klt, fqt=fqt, fields=fields, **kwargs,
        )
    except Exception as e:
        logger.error("Failed to fetch history from '%s': %s", src.name, e)
        raise DataFetchError(
            f"Failed to fetch history data from source '{src.name}'"
        ) from e

    # -- cache save (L1 + L2) --
    if df is not None and not df.empty:
        cache_set(cache_key, "history", df)

    return _validate_dataframe(df, fields)


def _get_stock_realtime(
    market: str,
    code: Union[str, list[str]],
    fields: Union[str, list[str]] = None,
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Fetch real-time quotes.

    Handles batch-vs-single-code dispatch based on the source's
    :attr:`~yquoter.plugin_base.DataSource.supports_batch_realtime` flag.

    Args:
        market: Market identifier.
        code: Single code or list of codes.
        fields: Fields to retrieve.
        source: Data source name or instance.
        **kwargs: Forwarded to the source.

    Returns:
        DataFrame with real-time quote data.
    """
    market = market.lower()

    if isinstance(code, str):
        code = [code]
    if isinstance(fields, str):
        fields = [fields]

    src = _resolve_source(source)

    if "realtime" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support realtime data."
        )

    # -- cache check (L1 only -- realtime is not persisted) --
    sorted_codes = tuple(sorted(code))
    sorted_fields = tuple(sorted(fields)) if fields else ()
    cache_key = make_cache_key(
        "realtime", source=src.name, market=market,
        code=sorted_codes, fields=sorted_fields,
    )
    cached = cache_get(cache_key, "realtime")
    if cached is not None:
        logger.info("Returning cached realtime for %s", market)
        return cached

    all_results: list[pd.DataFrame] = []

    if src.supports_batch_realtime:
        # Batch: pass all codes in a single call.
        try:
            df = src.get_realtime(
                market=market, code=code, fields=fields, **kwargs,
            )
            if df is not None and not df.empty:
                all_results.append(df)
        except Exception as e:
            logger.error("Batch realtime query from '%s' failed: %s", src.name, e)
            raise DataFetchError(
                f"Failed to fetch realtime data from source '{src.name}'"
            ) from e
    else:
        # Single-code iteration (e.g. TuShare).
        for single_code in code:
            try:
                df = src.get_realtime(
                    market=market, code=single_code, fields=fields, **kwargs,
                )
                if df is not None and not df.empty:
                    all_results.append(df)
            except Exception as e:
                logger.error(
                    "Realtime fetch for '%s' from '%s' failed: %s",
                    single_code, src.name, e,
                )
                continue

    if not all_results:
        logger.warning("All realtime fetch attempts returned empty data.")
        return pd.DataFrame()

    result_df = pd.concat(all_results, ignore_index=True)
    if not result_df.empty:
        cache_set(cache_key, "realtime", result_df)
    return result_df


def _get_stock_financials(
    market: str,
    code: str,
    end_day: str,
    report_type: str = "CWBB",
    limit: int = 12,
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Fetch financial statements.

    Args:
        market: Market identifier.
        code: Stock ticker symbol.
        end_day: Report period end date in ``YYYYMMDD`` format.
        report_type: Report type code.
        limit: Number of periods to fetch.
        source: Data source name or instance.
        **kwargs: Forwarded to the source.

    Returns:
        DataFrame with financial statement data.
    """
    market = market.lower()
    end_day = parse_date_str(end_day)
    logger.info("Fetching financials for %s:%s, type=%s", market, code, report_type)

    src = _resolve_source(source)

    if "financials" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support financials data."
        )

    # -- cache check (L1 -> L2) --
    cache_key = make_cache_key(
        "financials", source=src.name, market=market, code=code,
        end_day=end_day, report_type=report_type, limit=str(limit),
    )
    cached = cache_get(cache_key, "financials")
    if cached is not None:
        logger.info("Returning cached financials for %s:%s", market, code)
        return cached

    try:
        df = src.get_financials(
            market=market, code=code, end_day=end_day,
            report_type=report_type, limit=limit, **kwargs,
        )
    except Exception as e:
        logger.error("Failed to fetch financials from '%s': %s", src.name, e)
        raise DataFetchError(
            f"Failed to fetch financials from source '{src.name}'"
        ) from e

    if df is not None and not df.empty:
        cache_set(cache_key, "financials", df)
    return df


def _get_stock_profile(
    market: str,
    code: str,
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Fetch company profile information.

    Args:
        market: Market identifier.
        code: Stock ticker symbol.
        source: Data source name or instance.
        **kwargs: Forwarded to the source.

    Returns:
        DataFrame with company metadata.
    """
    market = market.lower()
    logger.info("Fetching profile for %s:%s", market, code)

    src = _resolve_source(source)

    if "profile" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support profile data."
        )

    # -- cache check (L1 -> L2) --
    cache_key = make_cache_key("profile", source=src.name, market=market, code=code)
    cached = cache_get(cache_key, "profile")
    if cached is not None:
        logger.info("Returning cached profile for %s:%s", market, code)
        return cached

    try:
        df = src.get_profile(market=market, code=code, **kwargs)
    except Exception as e:
        logger.error("Failed to fetch profile from '%s': %s", src.name, e)
        raise DataFetchError(
            f"Failed to fetch profile from source '{src.name}'"
        ) from e

    if df is not None and not df.empty:
        cache_set(cache_key, "profile", df)
    return df


def _get_stock_factors(
    market: str,
    code: str,
    trade_date: str,
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Fetch valuation / market factor data.

    Args:
        market: Market identifier.
        code: Stock ticker symbol.
        trade_date: Trading date in ``YYYYMMDD`` format.
        source: Data source name or instance.
        **kwargs: Forwarded to the source.

    Returns:
        DataFrame with factor metrics (PE, PB, etc.).
    """
    market = market.lower()
    trade_date = parse_date_str(trade_date)
    logger.info("Fetching factors for %s:%s on %s", market, code, trade_date)

    src = _resolve_source(source)

    if "factors" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support factors data."
        )

    # -- cache check (L1 -> L2) --
    cache_key = make_cache_key(
        "factors", source=src.name, market=market, code=code, trade_date=trade_date,
    )
    cached = cache_get(cache_key, "factors")
    if cached is not None:
        logger.info("Returning cached factors for %s:%s", market, code)
        return cached

    try:
        df = src.get_factors(
            market=market, code=code, trade_date=trade_date, **kwargs,
        )
    except Exception as e:
        logger.error("Failed to fetch factors from '%s': %s", src.name, e)
        raise DataFetchError(
            f"Failed to fetch factors from source '{src.name}'"
        ) from e

    if df is not None and not df.empty:
        cache_set(cache_key, "factors", df)
    return df


# ======================================================================
# Asynchronous dispatch functions  (internal, for reporting.py)
# ======================================================================


async def _aget_stock_history(
    market: str,
    code: str,
    start: str = None,
    end: str = None,
    klt: int = 101,
    fqt: int = 1,
    source: Optional[Union[str, DataSource]] = None,
) -> pd.DataFrame:
    """Async variant of :func:`_get_stock_history` (L1+L2 cached)."""
    from yquoter.config import FREQ_TO_KLT

    if start is None and end is None:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
    elif start is None:
        end = parse_date_str(end)
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=30)).strftime(
            "%Y%m%d"
        )
    elif end is None:
        start = parse_date_str(start)
        end = datetime.now().strftime("%Y%m%d")

    start = parse_date_str(start)
    end = parse_date_str(end)

    if isinstance(klt, str):
        klt = klt.lower()
        if klt not in FREQ_TO_KLT:
            raise ParameterError(f"Unknown frequency: {klt}")
        klt = FREQ_TO_KLT[klt]

    src = _resolve_source(source)

    if "history" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support history data."
        )

    # -- cache check (L1 -> L2) --
    cache_key = make_cache_key(
        "history", source=src.name, market=market, code=code,
        start=start, end=end, klt=str(klt), fqt=str(fqt),
    )
    cached = cache_get(cache_key, "history")
    if cached is not None:
        return cached

    df = await src.get_history_async(
        market=market, code=code, start=start, end=end, klt=klt, fqt=fqt,
    )

    if df is not None and not df.empty:
        cache_set(cache_key, "history", df)
    return df


async def _aget_stock_realtime(
    market: str,
    code: str,
    fields: list[str] = None,
    source: Optional[Union[str, DataSource]] = None,
) -> pd.DataFrame:
    """Async variant of :func:`_get_stock_realtime` (L1 cached)."""
    src = _resolve_source(source)

    if "realtime" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support realtime data."
        )

    # -- L1 cache check --
    sorted_fields = tuple(sorted(fields)) if fields else ()
    cache_key = make_cache_key(
        "realtime", source=src.name, market=market,
        code=(code,), fields=sorted_fields,
    )
    cached = cache_get(cache_key, "realtime")
    if cached is not None:
        return cached

    df = await src.get_realtime_async(
        market=market, code=code, fields=fields,
    )

    if df is not None and not df.empty:
        cache_set(cache_key, "realtime", df)
    return df


async def _aget_stock_profile(
    market: str,
    code: str,
    source: Optional[Union[str, DataSource]] = None,
) -> pd.DataFrame:
    """Async variant of :func:`_get_stock_profile` (L1+L2 cached)."""
    src = _resolve_source(source)

    if "profile" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support profile data."
        )

    cache_key = make_cache_key("profile", source=src.name, market=market, code=code)
    cached = cache_get(cache_key, "profile")
    if cached is not None:
        return cached

    df = await src.get_profile_async(market=market, code=code)

    if df is not None and not df.empty:
        cache_set(cache_key, "profile", df)
    return df


async def _aget_stock_factors(
    market: str,
    code: str,
    trade_date: str,
    source: Optional[Union[str, DataSource]] = None,
) -> pd.DataFrame:
    """Async variant of :func:`_get_stock_factors` (L1+L2 cached)."""
    src = _resolve_source(source)

    if "factors" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support factors data."
        )

    cache_key = make_cache_key(
        "factors", source=src.name, market=market, code=code, trade_date=trade_date,
    )
    cached = cache_get(cache_key, "factors")
    if cached is not None:
        return cached

    df = await src.get_factors_async(
        market=market, code=code, trade_date=trade_date,
    )

    if df is not None and not df.empty:
        cache_set(cache_key, "factors", df)
    return df


async def _aget_stock_financials(
    market: str,
    code: str,
    end_day: str,
    report_type: str = "CWBB",
    limit: int = 12,
    source: Optional[Union[str, DataSource]] = None,
    **kwargs,
) -> pd.DataFrame:
    """Async variant of :func:`_get_stock_financials` (L1+L2 cached)."""
    market = market.lower()
    end_day = parse_date_str(end_day)

    src = _resolve_source(source)

    if "financials" not in src.supported_types:
        raise DataSourceError(
            f"Data source '{src.name}' does not support financials data."
        )

    cache_key = make_cache_key(
        "financials", source=src.name, market=market, code=code,
        end_day=end_day, report_type=report_type, limit=str(limit),
    )
    cached = cache_get(cache_key, "financials")
    if cached is not None:
        return cached

    df = await src.get_financials_async(
        market=market, code=code, end_day=end_day,
        report_type=report_type, limit=limit, **kwargs,
    )

    if df is not None and not df.empty:
        cache_set(cache_key, "financials", df)
    return df
