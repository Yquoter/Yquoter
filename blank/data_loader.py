# blank/data_loader.py
"""Stream order-book data from Parquet, yielding one time_id window at a time."""

import logging
from typing import Iterator, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Columns needed from the parquet file (Level 1 bid/ask only)
_USE_COLS = [
    "time_id",
    "seconds_in_bucket",
    "bid_price1",
    "ask_price1",
    "bid_size1",
    "ask_size1",
    "stock_id",
]


def discover_stock_ids(parquet_path: str) -> List[int]:
    """Return sorted unique stock_id values from the parquet file.

    Reads only the stock_id column from the footer/metadata.
    """
    logger.info("Discovering stock IDs from %s", parquet_path)
    ids = (
        pd.read_parquet(parquet_path, columns=["stock_id"])["stock_id"]
        .unique()
        .tolist()
    )
    ids.sort()
    logger.info("Found %d unique stock IDs (range: %d – %d)", len(ids), ids[0], ids[-1])
    return ids


def discover_time_ids(parquet_path: str) -> List[int]:
    """Return sorted unique time_id values."""
    logger.info("Discovering time IDs from %s", parquet_path)
    tids = (
        pd.read_parquet(parquet_path, columns=["time_id"])["time_id"]
        .unique()
        .tolist()
    )
    tids.sort()
    logger.info("Found %d unique time IDs (range: %d – %d)", len(tids), tids[0], tids[-1])
    return tids


def iter_time_windows(
    parquet_path: str,
    time_ids: List[int],
) -> Iterator[Tuple[int, pd.DataFrame]]:
    """Generator: yield ``(time_id, DataFrame)`` for each requested time_id.

    Uses PyArrow predicate pushdown so only matching row groups are scanned.
    Only one window is held in memory at a time.

    Args:
        parquet_path: Path to ``book_train.parquet``.
        time_ids: Sorted list of time_ids to iterate (use :func:`discover_time_ids`).

    Yields:
        Tuple of ``(time_id, DataFrame)``. The DataFrame has columns:
        ``seconds_in_bucket``, ``bid_price1``, ``ask_price1``,
        ``bid_size1``, ``ask_size1``, ``stock_id``.
    """
    total = len(time_ids)
    for i, tid in enumerate(time_ids):
        df = pd.read_parquet(
            parquet_path,
            columns=_USE_COLS,
            filters=[("time_id", "=", tid)],
        )
        # Drop time_id column — it's constant within this window
        df = df.drop(columns=["time_id"])
        if i % 500 == 0:
            logger.info("Loaded time_id %d (%d/%d)", tid, i + 1, total)
        yield tid, df
