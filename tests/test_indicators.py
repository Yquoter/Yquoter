"""Tests for technical indicators (indicators.py).

Uses the sample_history_df fixture which provides 3 rows of known data.
"""

import pandas as pd
import pytest

from yquoter.indicators import (
    _get_ma_n,
    _get_rsi_n,
    _get_boll_n,
    _get_rv_n,
    _get_vol_ratio,
    _get_max_drawdown,
)
from tests.conftest import MockDataSource

sample_history_df = MockDataSource._history_df()


class TestIndicators:
    def test_ma_n_adds_column(self):
        df = _get_ma_n(df=sample_history_df, start="20260501", end="20260503", n=5)
        assert "MA5" in df.columns
        assert len(df) > 0

    def test_rsi_n_adds_column(self):
        df = _get_rsi_n(df=sample_history_df, start="20260501", end="20260503", n=14)
        assert "RSI14" in df.columns
        assert len(df) > 0

    def test_boll_n_adds_columns(self):
        df = _get_boll_n(df=sample_history_df, start="20260501", end="20260503", n=20)
        for col in ("upper", "mid", "lower"):
            assert col in df.columns

    def test_rv_n_adds_column(self):
        df = _get_rv_n(df=sample_history_df, start="20260501", end="20260503", n=5)
        assert "RV5" in df.columns
        assert len(df) > 0

    def test_vol_ratio_adds_column(self):
        df = _get_vol_ratio(df=sample_history_df, start="20260501", end="20260503", n=20)
        assert "vol_ratio20" in df.columns
        assert len(df) > 0

    def test_max_drawdown_returns_dict(self):
        result = _get_max_drawdown(df=sample_history_df, start="20260501", end="20260503")
        assert isinstance(result, dict)
        assert "max_drawdown" in result
        assert "max_drawdown_peak_date" in result
        assert "max_drawdown_trough_date" in result

    def test_ma_n_with_df_direct(self):
        """Calculate MA directly from a DataFrame (bypasses cache pipeline)."""
        df = _get_ma_n(df=sample_history_df, n=5)
        assert "MA5" in df.columns
        assert len(df) > 0
