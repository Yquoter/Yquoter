# blank/tensor_builder.py
"""Pack feature DataFrames into (N_stocks, 4, T) C-contiguous float32 tensors."""

import logging
from typing import List

import numpy as np
import pandas as pd

from blank.feature_engine import FEATURE_NAMES

logger = logging.getLogger(__name__)


def _determine_time_grid(df: pd.DataFrame) -> np.ndarray:
    """Extract the sorted unique seconds_in_bucket for a window.

    Returns a contiguous grid from min to max inclusive — gaps between
    observed seconds are treated as missing ticks (filled later).
    """
    secs = df.index.get_level_values(1).values
    min_s, max_s = int(np.min(secs)), int(np.max(secs))
    return np.arange(min_s, max_s + 1, dtype=np.int32)


def build_tensor(
    features_df: pd.DataFrame,
    stock_ids: List[int],
) -> np.ndarray:
    """Build a ``(N_stocks, 4, T)`` C-contiguous float32 tensor.

    Each stock's tick-level feature sequence is aligned to the global
    time grid (all observed seconds_in_bucket values across all stocks
    in this window). Missing ticks are forward-filled, with leading
    gaps filled with zeros.

    Feature channel order:
        ``[0]`` = WAP
        ``[1]`` = Bid-Ask Spread
        ``[2]`` = Volume Imbalance
        ``[3]`` = Log Return

    Args:
        features_df: Output of :func:`compute_features_for_window`.
            Index = ``(stock_id, seconds_in_bucket)``.
        stock_ids: Sorted list of all stock IDs (from :func:`discover_stock_ids`).

    Returns:
        ``np.ndarray`` of shape ``(len(stock_ids), 4, T)``, dtype ``float32``,
        C-contiguous, ready for zero-copy transfer to the GPU pipeline.
    """
    N = len(stock_ids)
    time_grid = _determine_time_grid(features_df)
    T = len(time_grid)
    sec_to_col = {int(s): i for i, s in enumerate(time_grid)}

    n_features = len(FEATURE_NAMES)
    tensor = np.zeros((N, n_features, T), dtype=np.float32, order="C")

    for si, sid in enumerate(stock_ids):
        try:
            stock_feats = features_df.xs(sid, level="stock_id", drop_level=True)
        except KeyError:
            # Stock has no data in this window — leave as zeros
            continue

        # Align: map observed seconds to tensor columns
        observed_secs = stock_feats.index.values.astype(np.int32)
        col_indices = np.array(
            [sec_to_col.get(int(s), -1) for s in observed_secs], dtype=np.int32
        )
        valid = col_indices >= 0
        if not valid.any():
            continue

        col_indices = col_indices[valid]
        for fi, fname in enumerate(FEATURE_NAMES):
            vals = stock_feats[fname].values[valid].astype(np.float32)
            tensor[si, fi, col_indices] = vals

        # Forward-fill along the time axis: each zero after a non-zero
        # in the same channel inherits the last non-zero value.
        for fi in range(n_features):
            row = tensor[si, fi, :]
            mask = row == 0.0
            idx = np.where(~mask, np.arange(T), 0)
            np.maximum.accumulate(idx, out=idx)
            tensor[si, fi, :] = row[idx]

    return np.ascontiguousarray(tensor)
