"""Tests for backward-compatibility wrappers (compat.py)."""

import warnings

import pandas as pd
import pytest

from tests.conftest import MockDataSource
from yquoter.compat import (
    get_stock_history,
    get_stock_realtime,
    get_stock_profile,
    get_stock_factors,
    get_stock_financials,
    get_ma_n,
    get_boll_n,
    get_rsi_n,
    get_rv_n,
    get_vol_ratio,
    get_max_drawdown,
    generate_stock_report,
)
from yquoter.datasource import _SOURCE_REGISTRY
from tests.conftest import MockDataSource


@pytest.fixture(autouse=True)
def _register_mock():
    _SOURCE_REGISTRY["compat_mock"] = MockDataSource()
    yield
    _SOURCE_REGISTRY.pop("compat_mock", None)


class TestDeprecationWarning:
    def test_get_stock_history_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            df = get_stock_history("cn", "MOCK", start="20260501", end="20260502",
                                   source="compat_mock")
            assert not df.empty

    def test_get_stock_realtime_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            df = get_stock_realtime("cn", "MOCK", source="compat_mock")
            assert not df.empty

    def test_get_stock_profile_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            df = get_stock_profile("cn", "MOCK", source="compat_mock")
            assert not df.empty

    def test_get_stock_factors_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            df = get_stock_factors("cn", "MOCK", trade_date="20260501",
                                   source="compat_mock")
            assert not df.empty

    def test_get_stock_financials_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            df = get_stock_financials("cn", "MOCK", end_day="20251231",
                                      source="compat_mock")
            assert not df.empty

    def test_ma_n_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            from yquoter.indicators import _get_ma_n
            df = get_ma_n(df=MockDataSource._history_df(), n=5)
            assert not df.empty

    def test_generate_report_triggers_warning(self):
        with pytest.warns(DeprecationWarning):
            report = generate_stock_report(
                market="cn", code="MOCK",
                start="20260501", end="20260503",
                source="compat_mock",
            )
            assert isinstance(report, str)
