# yquoter/cache.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""Multi-level cache system (L1 in-memory + L2 file).

Architecture::

    cache_get(key, data_type)
      |
      +--> L1 (in-memory OrderedDict + TTL)
      |      hit -> return df.copy()
      |      miss -> continue
      |
      +--> L2 (CSV file + TTL)  [skipped for realtime]
      |      hit -> promote to L1, return
      |      miss -> return None
      |
      +--> caller fetches from DataSource, calls cache_set()

L1 is per-data-type with independent LRU eviction and TTL.
L2 uses CSV files in ``.cache/{market}/{code}/`` (preserving the existing format).
"""

import os
import time
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from yquoter.config import get_cache_root, modify_df_path
from yquoter.exceptions import CacheSaveError, CacheDirectoryError, ParameterError
from yquoter.logger import get_logger

logger = get_logger(__name__)


# ======================================================================
# Default configuration
# ======================================================================

#: Per-data-type L1 cache limits and TTL (seconds).
_DEFAULT_L1_CONFIG: Dict[str, Dict[str, int]] = {
    "history":    {"max": 100, "ttl": 3600},      # 1 hour
    "profile":    {"max": 20,  "ttl": 86400},     # 1 day
    "factors":    {"max": 20,  "ttl": 3600},      # 1 hour
    "financials": {"max": 10,  "ttl": 86400},     # 1 day
    "realtime":   {"max": 5,   "ttl": 30},        # 30 seconds
}

#: Per-data-type L2 file TTL (seconds).  Real-time has no L2.
_DEFAULT_L2_TTL: Dict[str, int] = {
    "history":    86400,    # 1 day
    "profile":    604800,   # 7 days
    "factors":    86400,    # 1 day
    "financials": 604800,   # 7 days
}


# ======================================================================
# L1 In-Memory Cache
# ======================================================================


class _L1Cache:
    """Per-data-type in-memory LRU cache with TTL.

    Thread-safe.  All public methods acquire a per-instance lock.
    """

    def __init__(self, max_entries: int, default_ttl: int) -> None:
        """Initialize the L1 cache.

        Args:
            max_entries: Maximum number of entries before LRU eviction.
            default_ttl: Default TTL in seconds for entries in this cache.
        """
        self._max = max_entries
        self._ttl = default_ttl
        self._store: OrderedDict[Tuple, Tuple[float, pd.DataFrame]] = OrderedDict()
        self._lock = threading.Lock()

    # -- public API ---------------------------------------------------------

    def get(self, key: Tuple) -> Optional[pd.DataFrame]:
        """Retrieve an entry if it exists and has not expired.

        On hit, the entry is promoted to most-recently-used.
        Returns a **copy** of the DataFrame to prevent data races.
        """
        with self._lock:
            if key not in self._store:
                return None
            ts, df = self._store[key]
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                logger.debug("L1 TTL expired for key=%s", key)
                return None
            self._store.move_to_end(key)
            return df.copy()

    def set(self, key: Tuple, df: pd.DataFrame) -> None:
        """Insert or update an entry.

        Evicts the least-recently-used entry if *max_entries* is exceeded.
        Stores a **copy** of the DataFrame.
        """
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.monotonic(), df.copy())
            while len(self._store) > self._max:
                evicted_key, _ = self._store.popitem(last=False)
                logger.debug("L1 LRU evicted key=%s", evicted_key)

    def invalidate(self, key: Optional[Tuple] = None) -> None:
        """Remove an entry, or clear all entries when *key* is ``None``."""
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)

    @property
    def size(self) -> int:
        """Current number of entries in this cache."""
        with self._lock:
            return len(self._store)

    def __repr__(self) -> str:
        return f"_L1Cache(max={self._max}, ttl={self._ttl}s, size={self.size})"


# ======================================================================
# CacheManager (singleton)
# ======================================================================


class CacheManager:
    """Multi-level cache manager holding all L1 caches + L2 operations.

    This is a module-level singleton accessed via :func:`get_manager`.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._l1_caches: Dict[str, _L1Cache] = {}
        self._l1_config: Dict[str, Dict[str, int]] = {}
        self._l2_ttl: Dict[str, int] = {}
        self._lock = threading.Lock()

    # -- initialisation -----------------------------------------------------

    def initialize(
        self,
        l1_config: Optional[Dict[str, Dict[str, int]]] = None,
        l1_ttl: Optional[Dict[str, int]] = None,
        l1_max_entries: Optional[Dict[str, int]] = None,
        l2_ttl: Optional[Dict[str, int]] = None,
    ) -> None:
        """Initialise or reconfigure the cache manager.

        Args:
            l1_config: Complete L1 config dict (overrides defaults entirely).
                Structure: ``{"history": {"max": 100, "ttl": 3600}, ...}``.
            l1_ttl: Partial TTL overrides per data type.
                E.g. ``{"history": 1800}``.
            l1_max_entries: Partial max-entry overrides per data type.
                E.g. ``{"history": 200}``.
            l2_ttl: Partial L2 TTL overrides per data type.
                E.g. ``{"profile": 2592000}`` (30 days).
        """
        with self._lock:
            # Determine effective L1 config.
            if l1_config is not None:
                self._l1_config = {
                    k: dict(v) for k, v in l1_config.items()
                }
            else:
                self._l1_config = {
                    k: dict(v) for k, v in _DEFAULT_L1_CONFIG.items()
                }

            # Apply overrides.
            if l1_ttl:
                for dtype, ttl in l1_ttl.items():
                    if dtype in self._l1_config:
                        self._l1_config[dtype]["ttl"] = ttl
            if l1_max_entries:
                for dtype, mx in l1_max_entries.items():
                    if dtype in self._l1_config:
                        self._l1_config[dtype]["max"] = mx

            # Rebuild L1 caches.
            self._l1_caches = {}
            for dtype, cfg in self._l1_config.items():
                self._l1_caches[dtype] = _L1Cache(
                    max_entries=cfg["max"], default_ttl=cfg["ttl"],
                )

            # Effective L2 TTL config.
            self._l2_ttl = dict(_DEFAULT_L2_TTL)
            if l2_ttl:
                self._l2_ttl.update(l2_ttl)

            # Initialise the L2 file tracker (existing init_cache logic).
            init_cache()

            self._initialized = True
            logger.info(
                "CacheManager initialised: %d L1 caches, %d L2 types",
                len(self._l1_caches), len(self._l2_ttl),
            )

    # -- L1 operations ------------------------------------------------------

    def _l1(self, data_type: str) -> Optional[_L1Cache]:
        """Get the L1 cache for a data type, or ``None`` if unknown."""
        return self._l1_caches.get(data_type)

    def l1_get(self, data_type: str, key: Tuple) -> Optional[pd.DataFrame]:
        """L1 lookup.  Returns ``None`` on miss or expired."""
        cache = self._l1(data_type)
        if cache is None:
            return None
        return cache.get(key)

    def l1_set(self, data_type: str, key: Tuple, df: pd.DataFrame) -> None:
        """L1 insert."""
        cache = self._l1(data_type)
        if cache is not None:
            cache.set(key, df)

    def l1_invalidate(
        self, data_type: Optional[str] = None, key: Optional[Tuple] = None,
    ) -> None:
        """Invalidate L1 entries.

        * data_type is None — clears all L1 caches.
        * data_type="history", key=None — clears that type only.
        * data_type="history", key=(...) — clears specific key.
        """
        if data_type is None:
            for cache in self._l1_caches.values():
                cache.invalidate()
            logger.debug("L1 all caches cleared")
            return
        cache = self._l1(data_type)
        if cache is not None:
            cache.invalidate(key=key)
            logger.debug("L1 invalidated type=%s key=%s", data_type, key)

    # -- L2 operations ------------------------------------------------------

    def get_l2_path(self, data_type: str, key: Tuple) -> Optional[str]:
        """Convert a cache key into an L2 file path.

        Returns ``None`` for data types that have no L2 (e.g. realtime)
        or when the key structure is unrecognised.
        """
        root = get_cache_root()
        if data_type == "realtime":
            return None

        # Key format: (data_type_discriminator, market, code, ...)
        # We unpack based on the first element (discriminator).
        if not key or len(key) < 1:
            return None

        disc = key[0]
        if disc == "history" and len(key) >= 7:
            _, market, code, start, end, klt_str, fqt_str = key[:7]
            folder = os.path.join(root, market.lower(), code)
            return os.path.join(
                folder, f"{start}_{end}_klt{klt_str}_fqt{fqt_str}.csv",
            )

        if disc == "profile" and len(key) >= 3:
            _, market, code = key[:3]
            folder = os.path.join(root, market.lower(), code)
            return os.path.join(folder, "profile.csv")

        if disc == "factors" and len(key) >= 4:
            _, market, code, trade_date = key[:4]
            folder = os.path.join(root, market.lower(), code)
            return os.path.join(folder, f"factors_{trade_date}.csv")

        if disc == "financials" and len(key) >= 5:
            _, market, code, end_day, report_type = key[:5]
            limit = key[5] if len(key) > 5 else "12"
            folder = os.path.join(root, market.lower(), code)
            return os.path.join(
                folder, f"financials_{end_day}_{report_type}_{limit}.csv",
            )

        return None

    def _l2_ttl_for(self, data_type: str) -> int:
        """Get the L2 TTL for a data type (falls back to 1 day)."""
        return self._l2_ttl.get(data_type, 86400)

    def l2_get(self, data_type: str, key: Tuple) -> Optional[pd.DataFrame]:
        """L2 lookup: file path → TTL check → load CSV → promote to L1.

        Returns ``None`` on miss, expired, or unsupported type.
        """
        l2_path = self.get_l2_path(data_type, key)
        if l2_path is None or not os.path.isfile(l2_path):
            return None

        # TTL check using file mtime.
        ttl = self._l2_ttl_for(data_type)
        file_age = time.time() - os.path.getmtime(l2_path)
        if file_age > ttl:
            logger.debug("L2 TTL expired for %s (age=%.1fs > ttl=%ds)", l2_path, file_age, ttl)
            try:
                os.remove(l2_path)
            except OSError:
                pass
            _remove_from_file_list(l2_path)
            return None

        # Load.
        try:
            df = pd.read_csv(l2_path)
            if df.empty:
                return None
        except Exception as e:
            logger.warning("L2 load failed for %s: %s", l2_path, e)
            return None

        # Promote to L1.
        self.l1_set(data_type, key, df)
        modify_df_path(l2_path)
        logger.debug("L2 hit, promoted to L1: %s", l2_path)
        return df

    def l2_set(self, data_type: str, key: Tuple, df: pd.DataFrame) -> None:
        """L2 write: CSV file + file-list update (only for types that persist)."""
        if data_type == "realtime":
            return
        l2_path = self.get_l2_path(data_type, key)
        if l2_path is None:
            return

        folder = os.path.dirname(l2_path)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            logger.error("Failed to create L2 directory %s: %s", folder, e)
            raise CacheDirectoryError(
                f"Failed to create cache directory: {folder}",
            ) from e

        try:
            df.to_csv(l2_path, index=False)
        except Exception as e:
            logger.error("Failed to write L2 cache %s: %s", l2_path, e)
            raise CacheSaveError(f"Failed to save cache file: {l2_path}") from e

        _add_cache_file_list(l2_path)
        modify_df_path(l2_path)
        logger.debug("L2 saved: %s", l2_path)

    # -- combined L1+L2 operations ------------------------------------------

    def get(self, data_type: str, key: Tuple) -> Optional[pd.DataFrame]:
        """Try L1 then L2.  Returns ``None`` on complete miss."""
        # L1
        df = self.l1_get(data_type, key)
        if df is not None:
            return df

        # L2 (realtime has no L2)
        df = self.l2_get(data_type, key)
        if df is not None:
            return df

        return None

    def set(self, data_type: str, key: Tuple, df: pd.DataFrame) -> None:
        """Write to L1 and (unless realtime) L2."""
        if df is None or df.empty:
            return
        self.l1_set(data_type, key, df)
        self.l2_set(data_type, key, df)

    def invalidate(
        self, data_type: Optional[str] = None, key: Optional[Tuple] = None,
    ) -> None:
        """Invalidate L1 (and optionally L2) entries.

        When *key* is provided, the corresponding L2 file is also deleted.
        """
        self.l1_invalidate(data_type=data_type, key=key)
        if data_type is not None and key is not None:
            l2_path = self.get_l2_path(data_type, key)
            if l2_path and os.path.isfile(l2_path):
                try:
                    os.remove(l2_path)
                except OSError:
                    pass
                _remove_from_file_list(l2_path)
                logger.debug("L2 file deleted: %s", l2_path)


# ======================================================================
# Module-level singleton
# ======================================================================

_manager: Optional[CacheManager] = None
_manager_lock = threading.Lock()


def get_manager() -> CacheManager:
    """Get (or create) the module-level CacheManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = CacheManager()
    return _manager


# ======================================================================
# Cache key construction
# ======================================================================


def make_cache_key(data_type: str, **params: Any) -> Tuple:
    """Build a deterministic, hashable cache key from named parameters.

    The key always starts with *data_type* so that the L2 path generator
    can identify the structure without extra metadata.

    Examples::

        make_cache_key("history", market="cn", code="600519",
                       start="20260501", end="20260508", klt="101", fqt="1")
        # -> ("history", "cn", "600519", "20260501", "20260508", "101", "1")

        make_cache_key("profile", market="cn", code="600519")
        # -> ("profile", "cn", "600519")

        make_cache_key("realtime", market="cn",
                       code=("000001", "600519"),
                       fields=("close", "vol"))
        # -> ("realtime", "cn", ("000001", "600519"), ("close", "vol"))
    """
    return (data_type,) + tuple(
        tuple(sorted(v)) if isinstance(v, (list, set)) else v
        for v in params.values()
    )


# ======================================================================
# Unified cache API  (used by datasource.py dispatch functions)
# ======================================================================


def cache_get(key: Tuple, data_type: str) -> Optional[pd.DataFrame]:
    """Try L1 then L2.  Returns ``None`` on complete miss.

    Args:
        key: Cache key from :func:`make_cache_key`.
        data_type: Data type discriminator (``"history"``, ``"profile"``, ...).

    Returns:
        Cached DataFrame, or ``None``.
    """
    mgr = get_manager()
    return mgr.get(data_type, key)


def cache_set(key: Tuple, data_type: str, df: pd.DataFrame) -> None:
    """Write to L1 and (unless realtime) L2.

    No-op when *df* is ``None`` or empty.

    Args:
        key: Cache key from :func:`make_cache_key`.
        data_type: Data type discriminator.
        df: DataFrame to cache.
    """
    mgr = get_manager()
    mgr.set(data_type, key, df)


def cache_invalidate(
    data_type: Optional[str] = None,
    key: Optional[Tuple] = None,
) -> None:
    """Invalidate cached entries.

    * data_type=None — clears all L1 caches (L2 untouched).
    * data_type="history", key=None — clears that type's L1.
    * data_type="history", key=(...) — clears L1 entry and deletes
      the corresponding L2 file.
    """
    mgr = get_manager()
    mgr.invalidate(data_type=data_type, key=key)


# ======================================================================
# Legacy (L2-only) API  -- preserved unchanged for backward compatibility
# ======================================================================
#
# These functions are the original file-based cache system.  New code
# should use ``cache_get / cache_set`` instead.
# ======================================================================

#: Global list of ``(mtime, path)`` tuples tracking cached files.
_cache_file_list: List[Tuple[float, str]] = []
_cache_file_list_lock = threading.Lock()

#: Maximum number of L2 (file) cache entries across all data types.
_MAX_CACHE_ENTRIES = 5


def init_cache() -> None:
    """Scan the cache directory and populate the file list."""
    global _cache_file_list
    cache_root = get_cache_root()
    logger.info("Initialising L2 cache scan from: %s", cache_root)

    with _cache_file_list_lock:
        _cache_file_list = []
        for root, _dirs, files in os.walk(cache_root):
            for file in files:
                if file.endswith(".csv"):
                    path = os.path.join(root, file)
                    if os.path.exists(path):
                        mtime = os.path.getmtime(path)
                        _cache_file_list.append((mtime, path))

        _cache_file_list.sort(key=lambda x: x[0])
        _cleanup_old_cache()
    logger.info("L2 cache scan complete: %d files found", len(_cache_file_list))


def _add_cache_file_list(path: str) -> None:
    """Add a file to the L2 tracking list and enforce the max limit."""
    if not os.path.exists(path):
        logger.error("Cannot add non-existent file to L2 list: %s", path)
        return

    mtime = os.path.getmtime(path)
    with _cache_file_list_lock:
        for i, (existing_mtime, existing_path) in enumerate(_cache_file_list):
            if existing_path == path:
                _cache_file_list[i] = (mtime, path)
                break
        else:
            _cache_file_list.append((mtime, path))

        _cache_file_list.sort(key=lambda x: x[0])
        _cleanup_old_cache()


def _remove_from_file_list(path: str) -> None:
    """Remove a path from the tracking list (does not delete the file)."""
    with _cache_file_list_lock:
        for i, (_mtime, p) in enumerate(_cache_file_list):
            if p == path:
                _cache_file_list.pop(i)
                logger.debug("Removed from L2 file list: %s", path)
                return


def _cleanup_old_cache() -> None:
    """Delete the oldest L2 files when the count exceeds the maximum."""
    if len(_cache_file_list) <= _MAX_CACHE_ENTRIES:
        return

    files_to_delete = len(_cache_file_list) - _MAX_CACHE_ENTRIES
    deleted = 0
    for _ in range(files_to_delete):
        if not _cache_file_list:
            break
        _mtime, oldest_path = _cache_file_list.pop(0)
        try:
            if os.path.exists(oldest_path):
                os.remove(oldest_path)
                deleted += 1
        except Exception as e:
            logger.error("L2 eviction failed for %s: %s", oldest_path, e)

    if deleted:
        logger.info("L2 eviction: deleted %d old file(s)", deleted)


def set_max_cache_entries(max_entries: int) -> None:
    """Set the maximum number of L2 (file) cache entries.

    Args:
        max_entries: New maximum (must be >= 1).

    Raises:
        ParameterError: If *max_entries* is less than 1.
    """
    global _MAX_CACHE_ENTRIES
    if max_entries < 1:
        raise ParameterError("max_entries must be greater than 0")
    _MAX_CACHE_ENTRIES = max_entries
    _cleanup_old_cache()


def get_cache_path(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int,
    fqt: int,
    cache_root: Optional[str] = None,
) -> str:
    """Generate a history K-line cache file path.

    .. note::
       This is a legacy helper for history data.  New code should use
       :func:`make_cache_key` with :func:`cache_get` / :func:`cache_set`.

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        klt: K-line type code.
        fqt: Forward-adjustment type.
        cache_root: Root directory (defaults to configured cache root).

    Returns:
        Absolute path to the cache CSV file.
    """
    root = cache_root or get_cache_root()
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")
    folder = os.path.join(root, market.lower(), code)
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        raise CacheDirectoryError(
            f"Failed to create cache directory: {folder}",
        ) from e

    filename = f"{start_fmt}_{end_fmt}_klt{klt}_fqt{fqt}.csv"
    path = os.path.join(folder, filename)
    return path


def cache_exists(path: str) -> bool:
    """Check if a cache file exists on disk."""
    return os.path.isfile(path)


def load_cache(path: str) -> Optional[pd.DataFrame]:
    """Load a cached DataFrame from a CSV file.

    Returns ``None`` if the file is missing, empty, or corrupted.
    """
    if not cache_exists(path):
        return None
    try:
        df = pd.read_csv(path)
        return df if not df.empty else None
    except Exception as e:
        logger.warning("Failed to load cache %s: %s", path, e)
        return None


def save_cache(path: str, df: pd.DataFrame) -> None:
    """Save a DataFrame to a cache CSV file.

    Raises:
        CacheSaveError: If the file cannot be written.
    """
    try:
        df.to_csv(path, index=False)
        modify_df_path(path)
        _add_cache_file_list(path)
    except Exception as e:
        raise CacheSaveError(
            f"Failed to save cache file: {path}",
        ) from e
