# blank/pipeline_runner.py
"""CPU pipeline: stream parquet -> features -> tensors -> list of slices."""

import logging
import time
from typing import List, Optional

import numpy as np

from blank.data_loader import (
    discover_stock_ids,
    discover_time_ids,
    iter_time_windows,
)
from blank.feature_engine import compute_features_for_window
from blank.tensor_builder import build_tensor

logger = logging.getLogger(__name__)

_DEFAULT_PARQUET_PATH = (
    r"C:\Users\Xhang\Desktop\大三下\并行算法\大作业"
    r"\optiver-realized-volatility-prediction\book_train.parquet"
)


def run_cpu_pipeline(
    parquet_path: str = _DEFAULT_PARQUET_PATH,
    time_ids_subset: Optional[List[int]] = None,
) -> List[np.ndarray]:
    """Run the full CPU pipeline: stream data, compute features, build tensors.

    Processes time_id windows in ascending order. Each window produces one
    ``(N_stocks, 4, T)`` float32 C-contiguous tensor slice. Results are
    collected in a list for handoff to :func:`run_pipeline`.

    Args:
        parquet_path: Path to ``book_train.parquet``.
        time_ids_subset: Optional subset of time_ids to process (for
            testing or benchmarking). ``None`` processes all.

    Returns:
        List of ``np.ndarray``, each ``(N_stocks, 4, T)`` float32,
        in ascending time_id order.
    """
    t0 = time.perf_counter()

    # ---- pre-scan ----
    stock_ids = discover_stock_ids(parquet_path)
    all_time_ids = discover_time_ids(parquet_path)
    if time_ids_subset is not None:
        time_ids = sorted(time_ids_subset)
    else:
        time_ids = all_time_ids

    n_total = len(time_ids)
    n_stocks = len(stock_ids)
    logger.info(
        "CPU pipeline starting: %d time windows, %d stocks", n_total, n_stocks
    )

    # ---- main loop ----
    slices: List[np.ndarray] = []
    for i, (tid, df) in enumerate(iter_time_windows(parquet_path, time_ids)):
        feats = compute_features_for_window(df)
        tensor = build_tensor(feats, stock_ids)
        slices.append(tensor)

        if (i + 1) % 500 == 0:
            elapsed = time.perf_counter() - t0
            logger.info(
                "Processed %d/%d windows (%.1fs, %.0f windows/s)",
                i + 1,
                n_total,
                elapsed,
                (i + 1) / elapsed,
            )
        del df, feats  # free memory

    elapsed = time.perf_counter() - t0
    logger.info(
        "CPU pipeline done: %d slices, %.1f s total, %.0f windows/s",
        len(slices),
        elapsed,
        n_total / elapsed,
    )
    return slices
