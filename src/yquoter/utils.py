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
from typing import List
from yquoter.logger import get_logger
from yquoter.exceptions import CodeFormatError, DateFormatError
from yquoter.exceptions import DataFormatError
from yquoter.config import HISTORY_STANDARD_FIELDS_FULL, HISTORY_STANDARD_FIELDS_BASIC

logger = get_logger(__name__)

# Standardized columns for History-DataFrame format
def _validate_dataframe(df: pd.DataFrame, fields: str) -> pd.DataFrame:
    """Validate DataFrame structure against required columns.

    Args:
        df: DataFrame to validate.
        fields: Validation mode. Either ``"basic"`` or ``"full"``.

    Returns:
        pd.DataFrame: Validated DataFrame filtered to required columns.

    Raises:
        DataFormatError: If the DataFrame is empty or missing required
            columns.
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
    """Normalize a stock code.

    Removes leading/trailing whitespace and converts to uppercase.

    Args:
        code: Raw stock code.

    Returns:
        str: Normalized stock code.
    """
    return code.strip().upper()

def has_market_suffix(code: str) -> bool:
    """Check if a stock code contains a market suffix (e.g., ``.SH``).

    Args:
        code: Stock code to check.

    Returns:
        bool: ``True`` if the code has a market suffix, ``False`` otherwise.
    """
    return bool(re.match(r'^[\w\d]+\.([A-Z]{2,3})$', code))

def convert_code_to_tushare(code: str, market: str) -> str:
    """Convert a stock code to TuShare standard format.

    Args:
        code: Original stock code.
        market: Market identifier ('cn', 'hk', 'us').

    Returns:
        str: TuShare-formatted stock code with market suffix
            (e.g., ``"600000.SH"``).

    Raises:
        CodeFormatError: If the code format is unrecognized or the
            market is unknown.
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

def parse_date_str(date_str: str, fmt_out: str = "%Y%m%d") -> str:
    """Parse a date string into the specified output format.

    Supported input formats:
    - ``"2025-07-09"``
    - ``"2025/07/09"``
    - ``"20250709"``
    - ``"2025-07-09 23:00:00"``

    Args:
        date_str: Input date string to parse.
        fmt_out: Desired output format. Default is ``"%Y%m%d"``.

    Returns:
        str: Formatted date string in the specified output format.

    Raises:
        DateFormatError: If the date string cannot be parsed.
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
    """Load a file into a DataFrame based on its extension.

    Supports: csv, xlsx, json, parquet.

    Args:
        path: Path to the file to load.
        **kwargs: Additional keyword arguments passed to the corresponding
            pandas read function.

    Returns:
        pd.DataFrame: Loaded DataFrame.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file format is unsupported.
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
    """Filter a DataFrame to contain only the specified fields.

    Args:
        df: Source DataFrame.
        fields: List of field names to keep.

    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    if not fields:
        return df
    available = [f for f in fields if f in df.columns]
    missing = [f for f in fields if f not in df.columns]

    if missing:
        print("")

    return df[available]
def _is_interactive_session() -> bool:
    """Check if the code is running in an interactive terminal session.

    Returns:
        bool: ``True`` if running interactively (stdin is a TTY and not
            in CI), ``False`` otherwise.
    """
    # Check if stdin is a TTY and not running in a continuous integration environment (e.g., GitHub Actions)
    return sys.stdin.isatty() and not os.environ.get('CI')