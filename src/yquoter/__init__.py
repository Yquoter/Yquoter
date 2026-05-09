# yquoter/__init__.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""Yquoter: A unified financial data interface and analysis toolkit for CN/HK/US markets."""

__version__ = "0.4.0"
__author__ = "Yquoter Team"
__email__ = "yodeeshi@gmail.com"

import logging
from typing import Optional

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
from yquoter.logger import setup_logging, get_logger
setup_logging(level=logging.WARNING)
logger = get_logger(__name__)

# ----------------------------------------------------------------------
# Core imports
# ----------------------------------------------------------------------
from yquoter.llm_gateway import LLMGateway, LLMError, LLMNotAvailableError, LLMResponseError, normalize_provider_name
from yquoter.config import get_newest_df_path
from yquoter.datasource import register_source, set_default_source, discover_plugins
from yquoter.models import Stock
from yquoter.plugin_base import DataSource
from yquoter.exceptions import TuShareNotImportableError
from yquoter.compat import (
    get_stock_history,
    get_stock_realtime,
    get_stock_financials,
    get_stock_profile,
    get_stock_factors,
    get_rsi_n,
    get_max_drawdown,
    get_boll_n,
    get_rv_n,
    get_vol_ratio,
    get_ma_n,
    generate_stock_report
)

# ----------------------------------------------------------------------
# Cache initialization
# ----------------------------------------------------------------------
def init_cache_manager(
    max_entries: int = 50,
    l1_ttl: Optional[dict[str, int]] = None,
    l1_max_entries: Optional[dict[str, int]] = None,
    l2_ttl: Optional[dict[str, int]] = None,
) -> None:
    """Initialize the multi-level cache manager.

    Configures L1 (in-memory) and L2 (file) caches for all data types.
    Defaults are sensible for most users; override individual TTLs or
    entry limits via the optional parameters.

    Args:
        max_entries: Maximum number of L2 (file) cache entries across
            all data types.  Default 50.
        l1_ttl: Per-data-type L1 TTL overrides in seconds.
            E.g. ``{"history": 1800, "realtime": 15}``.
        l1_max_entries: Per-data-type L1 max-entry overrides.
            E.g. ``{"history": 200}``.
        l2_ttl: Per-data-type L2 (file) TTL overrides in seconds.
            E.g. ``{"profile": 2592000}`` (30 days).
    """
    from yquoter.cache import get_manager, set_max_cache_entries, init_cache as l2_init_cache

    # L2 file cache config (existing).
    set_max_cache_entries(max_entries)
    l2_init_cache()

    # L1 + L2 multi-level config via CacheManager.
    mgr = get_manager()
    mgr.initialize(
        l1_ttl=l1_ttl,
        l1_max_entries=l1_max_entries,
        l2_ttl=l2_ttl,
    )

    logging.getLogger(__name__).info(
        "Cache manager initialised: max_entries=%s, l1=%d types, l2=%d types",
        max_entries,
        len(mgr._l1_caches) if hasattr(mgr, '_l1_caches') else 0,
        len(mgr._l2_ttl) if hasattr(mgr, '_l2_ttl') else 0,
    )


# Auto-initialize cache (safe-guarded)
try:
    init_cache_manager()
except Exception as e:
    logging.getLogger(__name__).warning(f"Cache manager init failed: {e}")

# Auto-discover DataSource plugins via entry_points.
try:
    discover_plugins()
except Exception as e:
    logging.getLogger(__name__).warning(f"Plugin discovery failed: {e}")


# ----------------------------------------------------------------------
# LLM Gateway (auto-detect from environment)
# ----------------------------------------------------------------------
def get_llm_gateway() -> LLMGateway:
    """Get the LLM gateway instance for AI-powered analysis.

    Automatically detects configured providers from environment variables
    (e.g., ``DEEPSEEK_API_KEY``, ``OPENAI_API_KEY``).

    Returns:
        LLMGateway: The LLM gateway instance.

    Example:
        >>> from yquoter import get_llm_gateway
        >>> gateway = get_llm_gateway()
        >>> if gateway.is_available():
        ...     result = gateway.analyze(
        ...         system_prompt="You are an analyst.",
        ...         user_prompt="Analyze this stock..."
        ...     )
    """
    return LLMGateway()


# ----------------------------------------------------------------------
# TuShare initialization
# ----------------------------------------------------------------------
def init_tushare(token: str = None) -> None:
    """Initialize the Tushare data source.

    Args:
        token: Tushare API token. If ``None``, attempts to load from
            environment variables.

    Raises:
        TuShareNotImportableError: If the Tushare library is not
            installed.
        ImportError: If the ``tushare_source`` module is missing.
        ConfigError: If no token is available.
        TuShareAPIError: If token validation fails.
    """
    try:
        from .tushare_source import init_tushare as _ts_init
        _ts_init(token)
    except TuShareNotImportableError as e:
        logger.error(
            "Tushare library not found. Please install it to use the Tushare data source: "
            "pip install yquoter[tushare] or pip install tushare"
        )
        raise e
    except ImportError:
        logger.error("Failed to load tushare_source module. Check package integrity.")
        raise

# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
__all__ = [
    "register_source",
    "set_default_source",
    "init_tushare",
    "init_cache_manager",
    "Stock",
    "DataSource",
    # LLM
    "get_llm_gateway",
    "LLMGateway",
    "LLMError",
    "normalize_provider_name",
    # Legacy compat API
    "get_stock_history",
    "get_stock_realtime",
    "get_stock_factors",
    "get_stock_profile",
    "get_stock_financials",
    "get_ma_n",
    "get_boll_n",
    "get_max_drawdown",
    "get_vol_ratio",
    "get_newest_df_path",
    "get_rsi_n",
    "get_rv_n",
    "generate_stock_report",
]

