# yquoter/utils.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import re
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Optional, Literal, List
from yquoter.logger import get_logger
from yquoter.exceptions import CodeFormatError, ConfigError, DateFormatError
from yquoter.exceptions import DataSourceError, ParameterError, DataFetchError, DataFormatError
from yquoter.config import HISTORY_STANDARD_FIELDS_FULL, HISTORY_STANDARD_FIELDS_BASIC

logger = get_logger(__name__)

# Standardized columns for History-DataFrame format
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
        missing = [col for col in HISTORY_STANDARD_FIELDS_FULL if col not in df.columns]
        _REQUIRED_COLUMNS = HISTORY_STANDARD_FIELDS_FULL
    elif fields == "basic":
        missing = [col for col in HISTORY_STANDARD_FIELDS_BASIC if col not in df.columns]
        _REQUIRED_COLUMNS = HISTORY_STANDARD_FIELDS_BASIC
    if missing:
        logger.error(f"Missing required columns: {missing}")
        raise DataFormatError(f"Data source returned invalid format: Missing columns {missing}; required columns are {_REQUIRED_COLUMNS}")
    df = df[_REQUIRED_COLUMNS]
    logger.info(f"Data validation passed for {fields} fields")
    return df


# ---------- Stock Code Tools ----------

def normalize_code(code: str) -> str:
    """
    Normalize stock code by removing whitespace and converting to uppercase
    """
    return code.strip().upper()

def has_market_suffix(code: str) -> bool:
    """
    Check if stock code contains market suffix
    """
    return bool(re.match(r'^[\w\d]+\.([A-Z]{2,3})$', code))

def convert_code_to_tushare(
    code: str, 
    market: str
) -> str:
    """
    Convert stock code to TuShare standard format based on market type

        Args:
            code: Original stock code
            market: Market identifier ('cn', 'hk', 'us')

        Returns:
            TuShare-formatted stock code with market suffix

        Raises:
            CodeFormatError: If code format is unrecognized or market is unknown
    """
    logger.info(f"Converting {code} to TuShare format")
    market.strip().lower()
    code = normalize_code(code)
    if has_market_suffix(code):
        logger.info(f"{code} is already in TuShare format")
        return code
    if market == 'cn':
        if code.startswith('6'):
            code = f"{code}.SH"
        elif code.startswith(('0', '3')):
            code = f"{code}.SZ"
        elif code.startswith('9'):
            code = f"{code}.BJ"
        else:
            logger.error(f"Unrecognized A-share code format: {code}")
            raise CodeFormatError(f"Unrecognized A-share code format: {code}")
    elif market == 'hk':
        code_padded = code.zfill(5)
        code = f"{code_padded}.HK"
        logger.info(f"Converted to TuShare format: {code}")
    elif market == 'us':
        code = f"{code}.US"
        logger.info(f"Converted to TuShare format: {code}")
    else:
        logger.error(f"Unknown market type: {code}")
        raise CodeFormatError(f"Unknown market type: {market}")
    return code

# ---------- Date Processing Tools ----------

def parse_date_str(
    date_str: str, 
    fmt_out: str = "%Y%m%d"
) -> str:
    """
    Parse various common date string formats into specified output format

        Supported input formats:
        - '2025-07-09'
        - '2025/07/09'
        - '20250709'
        - '2025-07-09 23:00:00'

        Args:
            date_str: Input date string to parse
            fmt_out: Desired output format (default: '%Y%m%d')

        Returns:
            Formatted date string in specified output format

        Raises:
            DateFormatError: If date format cannot be recognized
    """
    date_str = date_str.strip()
    fmts_in = ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts_in:
        try:
            dt = datetime.strptime(date_str, fmt)
            formatted = dt.strftime(fmt_out)
            logger.info(f"Successfully parsed date: {date_str} -> {formatted}")
            return formatted
        except ValueError:
            # Try next format if current one fails
            continue
    logger.error(f"Unrecognized date format: {date_str}")
    raise DateFormatError(f"Unrecognized date format: {date_str}")


def load_file_to_df(path: str, **kwargs) -> pd.DataFrame:
    """
    Automatically load file into DataFrame based on file extension

        Supports: csv / xlsx / json / parquet
        Additional parameters are passed to corresponding pandas read functions

        Args:
            path: Path to the file to load
           ** kwargs: Additional parameters for pandas read functions

        Returns:
            DataFrame containing at least ['date', 'close'] columns

        Raises:
            FileNotFoundError: If specified file does not exist
            ValueError: If file format is unsupported or required columns are missing
    """
    if not os.path.exists(path):
        logger.error(f"File not found: {path}")
        raise FileNotFoundError(f"File not found: {path}")

    ext = os.path.splitext(path)[-1].lower()

    if ext == ".csv":
        df = pd.read_csv(path, **kwargs)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(path, **kwargs)
    elif ext == ".json":
        df = pd.read_json(path, **kwargs)
    elif ext == ".parquet":
        df = pd.read_parquet(path, **kwargs)
    else:
        logger.error(f"Unsupported file format: {ext}")
        raise ValueError(f"Unsupported file format: {ext}")

    if not df.empty:
        logger.info(f"Loaded file: {path}")
    else:
        logger.warning(f"File loaded with no data: {path}")

    # Standardize date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce",format="%Y%m%d")
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    return _validate_dataframe(df, fields="full")

def filter_fields(df: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
    """
    Filter DataFrame to contain only specified fields

        Args:
            df: Source DataFrame from data source
            fields: List of fields that user wants to keep

        Returns:
            DataFrame containing only the specified fields
    """
    if not fields:
        return df
    available = [f for f in fields if f in df.columns]
    missing = [f for f in fields if f not in df.columns]

    if missing:
        print("")

    return df[available]
def _is_interactive_session() -> bool:
    """Checks if the code is running in an interactive terminal session."""
    # Check if stdin is a TTY and not running in a continuous integration environment (e.g., GitHub Actions)
    return sys.stdin.isatty() and not os.environ.get('CI')