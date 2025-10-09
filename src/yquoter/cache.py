# yquoter/cache.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import pandas as pd
from typing import Optional
from yquoter.logger import get_logger
from yquoter.config import get_cache_root, modify_df_path
from yquoter.exceptions import CacheSaveError, CacheDirectoryError, ParameterError

# Log Configuration
logger = get_logger(__name__)

# Global cache management variables
_cache_file_list = []  # List of cached file paths
_MAX_CACHE_ENTRIES = 5  # Default maximum cache entries

def init_cache():
    """
    Initialize cache manager, scan cache directory and load file list
    """
    global _cache_file_list
    cache_root = get_cache_root()
    logger.info(f"Starting cache manager initialization, using root directory: {cache_root}")
    # Clear existing list
    _cache_file_list = []

    # Traverse all CSV files in cache directory
    for root, dirs, files in os.walk(cache_root):
        for file in files:
            if file.endswith('.csv'):
                path = os.path.join(root, file)
                if os.path.exists(path):  # Ensure file exists
                    # Get file modification time as cache time
                    mtime = os.path.getmtime(path)
                    _cache_file_list.append((mtime, path))

    # Sort by modification time (old -> new)
    _cache_file_list.sort(key=lambda x: x[0])
    logger.info(f"Cache manager initialized, found {len(_cache_file_list)} cached files")

    # Perform initial cleanup if exceeding limit
    _cleanup_old_cache()


def _add_cache_file_list(path: str):
    """
    Add new cache file to management list and perform cleanup (internal function)
    """
    global _cache_file_list
    logger.info(f"Adding cache file to management system: {path}")
    if not os.path.exists(path):
        logger.error(f"Cannot add non-existent cache file: {path}")
        return

    mtime = os.path.getmtime(path)

    # Check if exists and update if found
    for i, (existing_mtime, existing_path) in enumerate(_cache_file_list):
        if existing_path == path:
            _cache_file_list[i] = (mtime, path)
            logger.info(f"Updated existing cache entry: {path} (new modification time recorded)")
            break
    else:
        # Add if not exists
        _cache_file_list.append((mtime, path))
        logger.info(f"Added new cache entry: {path} to management list")

    # Sort by modification time
    _cache_file_list.sort(key=lambda x: x[0])

    # Clean up old cache
    _cleanup_old_cache()


def _cleanup_old_cache():
    """
    Clean up old cache files exceeding quantity limit
    """
    global _cache_file_list
    logger.info(f"Starting cache cleanup check - max allowed: {_MAX_CACHE_ENTRIES}")
    # Calculate number of files to delete
    if len(_cache_file_list) <= _MAX_CACHE_ENTRIES:
        logger.info("No cache cleanup needed (current entries under limit)")
        return

    files_to_delete = len(_cache_file_list) - _MAX_CACHE_ENTRIES
    deleted_count = 0
    logger.info(f"Cache cleanup required - need to delete {files_to_delete} oldest file(s)")

    # Delete oldest files
    for _ in range(files_to_delete):
        if not _cache_file_list:
            break

        _, oldest_path = _cache_file_list.pop(0)
        try:
            if os.path.exists(oldest_path):
                os.remove(oldest_path)
                logger.info(f"Cache cleanup: Deleted old file {oldest_path}")
                deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to delete cache file: {oldest_path}, error: {e}")

    if deleted_count > 0:
        logger.info(f"Cache cleanup completed: Deleted {deleted_count} old files")


def set_max_cache_entries(max_entries: int):
    """
    Set maximum cache entries and perform cleanup
    """
    global _MAX_CACHE_ENTRIES
    logger.info(f"Received request to set maximum cache entries to: {max_entries}")
    if max_entries < 1:
        logger.error(f"Invalid maximum cache entries value: {max_entries} (must be greater than 0)")
        raise ParameterError("Maximum cache entries must be greater than 0")
    _MAX_CACHE_ENTRIES = max_entries
    logger.info(f"Successfully updated maximum cache entries to: {max_entries}")

    # Perform immediate cleanup
    _cleanup_old_cache()


def get_cache_path(
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int,
        fqt: int,
        cache_root: Optional[str] = None
) -> str:
    """
    Generate cache file path based on market, code and time range
    """
    logger.info(f"Generating cache path - market: {market}, stock code: {code}, time range: {start} to {end}")
    root = cache_root or get_cache_root()
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")
    folder = os.path.join(root, market.lower(), code)
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create cache directory: {folder}, exception: {e}")
        raise CacheDirectoryError(f"Failed to create cache directory: {folder}") from e

    filename = f"{start_fmt}_{end_fmt}_klt{klt}_fqt{fqt}.csv"
    path = os.path.join(folder, filename)
    logger.info(f"Generated cache path: {path}")
    return path


def cache_exists(path: str) -> bool:
    """
    Check if cache file exists at specified path
    """
    exists = os.path.isfile(path)
    logger.info(f"Cache file check - path: {path}, exists: {'Yes' if exists else 'No'}")
    return exists


def load_cache(path: str) -> Optional[pd.DataFrame]:
    """
    Read data from cache file into DataFrame, return None on failure
    """
    logger.info(f"Starting to load cache file: {path}")
    if not cache_exists(path):
        logger.warning(f"Cache file does not exist, cannot load: {path}")
        return None
        # Silent failure design pattern for load cache operations
    try:
        df = pd.read_csv(path)
        if df.empty:
            logger.warning(f"Cache file is empty: {path}")
            return None

        logger.info(f"Successfully loaded cache file: {path}")
        return df
    except Exception as e:
        logger.error(f"Failed to load cache file: {path}, exception: {e}")
        return None


def save_cache(path: str, df: pd.DataFrame):
    """
    Save DataFrame to cache file
    """
    logger.info(f"Starting to save cache file: {path}")
    try:
        df.to_csv(path, index=False)
        logger.info(f"Successfully saved cache file: {path}")
        modify_df_path(path)
        # Add to cache management system
        _add_cache_file_list(path)

    except Exception as e:
        logger.error(f"Failed to save cache file: {path}, exception: {e}")
        # Throw specific exception after logging
        raise CacheSaveError(f"Failed to save cache file: {path}") from e