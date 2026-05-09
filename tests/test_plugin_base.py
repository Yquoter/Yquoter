"""Tests for the DataSource plugin base and built-in implementations."""

import pandas as pd
import pytest

from yquoter.plugin_base import DataSource
from yquoter.exceptions import DataSourceError
from yquoter.spider_source import SpiderDataSource
from yquoter.tushare_source import TushareDataSource
from tests.conftest import MockDataSource


# ======================================================================
# DataSource ABC
# ======================================================================


class TestDataSourceABC:
    def test_abstract_class_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            DataSource()  # noqa: abstract

    def test_default_methods_raise(self):
        # A minimal concrete subclass with only name defined.
        class Minimal(DataSource):
            @property
            def name(self):
                return "minimal"

        ds = Minimal()
        with pytest.raises(DataSourceError, match="does not support"):
            ds.get_history("cn", "X", "20250101", "20250102")


class TestMockDataSource:
    """The MockDataSource from conftest should serve as a reference."""

    def test_all_methods_return_dataframe(self, mock_source):
        df_h = mock_source.get_history("cn", "MOCK", "20250101", "20250102")
        assert isinstance(df_h, pd.DataFrame)
        assert len(df_h) == 3

        df_rt = mock_source.get_realtime("cn", "MOCK")
        assert isinstance(df_rt, pd.DataFrame)
        assert not df_rt.empty

    def test_supported_types(self, mock_source):
        types = mock_source.supported_types
        assert "history" in types
        assert "realtime" in types

    def test_batch_realtime_default(self, mock_source):
        assert mock_source.supports_batch_realtime is True


# ======================================================================
# SpiderDataSource
# ======================================================================


class TestSpiderDataSource:
    def test_identity(self):
        ds = SpiderDataSource()
        assert ds.name == "spider"

    def test_supports_all_types(self):
        ds = SpiderDataSource()
        assert ds.supported_types == {
            "history", "realtime", "financials", "profile", "factors",
        }

    def test_batch_realtime_enabled(self):
        ds = SpiderDataSource()
        assert ds.supports_batch_realtime is True

    def test_get_history_returns_dataframe(self):
        ds = SpiderDataSource()
        df = ds.get_history("cn", "600519", "20260501", "20260502")
        assert isinstance(df, pd.DataFrame)

    def test_get_profile_returns_dataframe(self):
        ds = SpiderDataSource()
        df = ds.get_profile("cn", "600519")
        assert isinstance(df, pd.DataFrame)


# ======================================================================
# TushareDataSource
# ======================================================================


class TestTushareDataSource:
    def test_identity(self):
        ds = TushareDataSource()
        assert ds.name == "tushare"

    def test_supports_history_and_realtime_only(self):
        ds = TushareDataSource()
        assert ds.supported_types == {"history", "realtime"}

    def test_batch_realtime_disabled(self):
        ds = TushareDataSource()
        assert ds.supports_batch_realtime is False

    def test_init_hint_present(self):
        ds = TushareDataSource()
        hint = ds.initialization_hint
        assert hint is not None
        assert "init_tushare" in hint

    def test_unsupported_type_raises(self):
        ds = TushareDataSource()
        # Profile is not in supported_types.
        with pytest.raises(DataSourceError):
            ds.get_profile("cn", "600519")

    def test_get_history_raises_without_init(self):
        ds = TushareDataSource()
        with pytest.raises(Exception):
            ds.get_history("cn", "600519", "20260501", "20260502")
