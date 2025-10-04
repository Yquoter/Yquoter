import re
import pandas as pd
from yquoter.logger import get_logger
from datetime import datetime
from typing import Optional, Literal, List
import os
from yquoter.exceptions import CodeFormatError, DateFormatError
# ---------- Log Configuration ----------
logger = get_logger(__name__)


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
    market.strip().lower()
    code = normalize_code(code)
    if has_market_suffix(code):
        return code
    if market == 'cn':
        if code.startswith('6'):
            code = f"{code}.SH"
        elif code.startswith(('0', '3')):
            code = f"{code}.SZ"
        elif code.startswith('9'):
            code = f"{code}.BJ"
        raise CodeFormatError(f"Unrecognized A-share code format: {code}")
    elif market == 'hk':
        code_padded = code.zfill(5)
        code = f"{code_padded}.HK"
    elif market == 'us':
        code = f"{code}.US"
    else:
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
            logger.debug(f"Successfully parsed date: {date_str} -> {formatted}")
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
        raise ValueError(f"Unsupported file format: {ext}")

    # Validate required columns
    if "date" not in df.columns:
        raise ValueError("Data is missing required 'date' column")
    if "close" not in df.columns:
        raise ValueError("Data is missing required 'close' column")

    # Standardize date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce",format="%Y%m%d")
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    return df

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