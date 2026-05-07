# yquoter/exceptions.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""
This module defines all custom exception types for the yquoter project.
"""

class YquoterError(Exception):
    """Base exception class for all yquoter custom errors.

    All project-specific exceptions inherit from this class, allowing
    users to catch only this base exception to handle all known errors.
    """
    pass

class CodeFormatError(YquoterError, ValueError):
    """Raised when a stock code format cannot be recognized or processed.

    Inherits from ``ValueError`` for semantic compatibility.
    """
    pass

class CacheError(YquoterError):
    """Base exception for cache-related errors."""
    pass

class CacheSaveError(CacheError):
    """Raised when saving a cache file fails."""
    pass

class CacheDirectoryError(CacheError):
    """Raised when the cache directory cannot be created."""
    pass

class ConfigError(YquoterError):
    """Raised when a configuration item is missing or has an invalid format."""
    pass

class DateFormatError(YquoterError, ValueError):
    """Raised when a date string format cannot be recognized or processed.

    Inherits from ``ValueError`` for semantic compatibility.
    """
    pass

class DataSourceError(YquoterError):
    """Raised for errors related to data sources.

    Examples include non-existent or uninitialized data sources.
    """
    pass

class DataFetchError(YquoterError):
    """Raised when fetching data from an external source fails."""
    pass

class DataFormatError(YquoterError):
    """Raised when the format of fetched data does not meet requirements."""
    pass

class IndicatorCalculationError(YquoterError):
    """Raised when a technical indicator calculation fails."""
    pass

class ParameterError(YquoterError, ValueError):
    """Raised when API parameters are invalid."""
    pass

class PathNotFoundError(YquoterError, FileNotFoundError):
    """Raised when a required file or directory path does not exist.

    Inherits from ``FileNotFoundError`` for standard exception
    compatibility.
    """
    pass

class PlotLibImportError(YquoterError):
    """Raised when importing matplotlib or mplfinance fails."""
    pass

class TuShareAPIError(YquoterError):
    """Raised when the Tushare token is invalid or has insufficient permissions."""
    pass

class TuShareNotImportableError(YquoterError):
    """Raised when the Tushare package cannot be imported."""
    pass

# Add more exceptions here as needed in the future, e.g.:
# class DataNotFoundError(YquoterError):
#     """Raised when the requested data does not exist."""
#     pass