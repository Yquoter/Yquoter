# blank/feature_engine.py
"""Compute 4 high-frequency order-book features for each stock per time window."""

import logging
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_NAMES: List[str] = ["wap", "spread", "vol_imb", "log_ret"]


def _compute_stock_features(stock_df: pd.DataFrame) -> pd.DataFrame:
    """Compute 4 features for one stock's tick-level data within a time_id window.

    Args:
        stock_df: Rows for a single stock_id within one time_id window.
            Must have columns: ``seconds_in_bucket``, ``bid_price1``,
            ``ask_price1``, ``bid_size1``, ``ask_size1``.

    Returns:
        DataFrame indexed by seconds_in_bucket with columns
        ``wap``, ``spread``, ``vol_imb``, ``log_ret``.
    """
    if len(stock_df) == 0:
        return pd.DataFrame(
            columns=["wap", "spread", "vol_imb", "log_ret"],
            index=pd.Index([], name="seconds_in_bucket"),
        )

    df = stock_df.sort_values("seconds_in_bucket").copy()

    bid_p = df["bid_price1"].values
    ask_p = df["ask_price1"].values
    bid_q = df["bid_size1"].values.astype(np.float64)
    ask_q = df["ask_size1"].values.astype(np.float64)

    # WAP = (bid_p * bid_q + ask_p * ask_q) / (bid_q + ask_q)
    denom = bid_q + ask_q
    with np.errstate(invalid="ignore", divide="ignore"):
        wap = np.where(denom > 0, (bid_p * bid_q + ask_p * ask_q) / denom, 0.0)

    # Bid-Ask Spread = ask_p - bid_p
    spread = ask_p - bid_p

    # Volume Imbalance = (bid_q - ask_q) / (bid_q + ask_q)
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_imb = np.where(denom > 0, (bid_q - ask_q) / denom, 0.0)

    # Log Return based on WAP
    log_ret = np.empty_like(wap)
    log_ret[0] = 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = wap[1:] / wap[:-1]
        log_ret[1:] = np.where(
            (ratio > 0) & np.isfinite(ratio),
            np.log(ratio),
            0.0,
        )

    return pd.DataFrame(
        {
            "wap": wap,
            "spread": spread,
            "vol_imb": vol_imb,
            "log_ret": log_ret,
        },
        index=df["seconds_in_bucket"].values,
    )


def compute_features_for_window(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 4 features for every stock in a single time_id window.

    Args:
        df: DataFrame for one time_id window. Must have columns:
            ``seconds_in_bucket``, ``bid_price1``, ``ask_price1``,
            ``bid_size1``, ``ask_size1``, ``stock_id``.

    Returns:
        DataFrame indexed by ``(stock_id, seconds_in_bucket)``
        with columns ``wap``, ``spread``, ``vol_imb``, ``log_ret``.
    """
    result = (
        df.groupby("stock_id", sort=False, observed=True)
        .apply(_compute_stock_features, include_groups=False)
    )
    return result
