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
    """
    Base custom exception class for the project.
    All other custom exceptions in the project should inherit from this class,
    allowing users to catch only this base exception to handle all known project errors.
    """
    pass

class CodeFormatError(YquoterError, ValueError):
    """
    Raised when the stock code format cannot be recognized or processed.
    Inherits from ValueError to maintain partial semantic compatibility.
    """
    pass

class DateFormatError(YquoterError, ValueError):
    """
    Raised when the date string format cannot be recognized or processed.
    Inherits from ValueError to maintain partial semantic compatibility.
    """
    pass

class CacheError(YquoterError):
    """Base exception related to cache operations."""
    pass

class CacheSaveError(CacheError):
    """Raised when saving cache fails."""
    pass

class CacheDirectoryError(CacheError):
    """Raised when creating a cache directory fails."""
    pass

class ConfigError(YquoterError):
    """Raised when a configuration item is missing or has an invalid format."""
    pass


class DataSourceError(YquoterError):
    """
    Errors related to data sources, such as non-existent or uninitialized data sources.
    """
    pass

class ParameterError(YquoterError, ValueError):
    """Raised when the parameters provided to the API are invalid."""
    pass

class PathNotFoundError(YquoterError, FileNotFoundError):
    """Raised when a required file or directory path does not exist.
    Inherits from FileNotFoundError for standard exception compatibility.
    """
    pass

class DataFetchError(YquoterError):
    """Raised when fetching data from an external data source fails."""
    pass

class DataFormatError(YquoterError):
    """Raised when the format of fetched data does not meet requirements."""
    pass

class IndicatorCalculationError(YquoterError):
    """Raised when an error occurs during technical indicator calculation."""
    pass

class TuShareAPIError(YquoterError):
    """Raised when a tuShare token is invalid or Not enough permission."""
    pass

class TuShareNotImportableError(YquoterError):
    """Raised when failing to import TuShare."""
    pass

# Add more exceptions here as needed in the future, e.g.:
# class DataNotFoundError(YquoterError):
#     """Raised when the requested data does not exist."""
#     pass