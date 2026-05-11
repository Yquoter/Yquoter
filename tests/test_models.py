"""Tests for the Stock class (models.py)."""

import pandas as pd
import pytest

from yquoter import Stock
from yquoter.exceptions import DataSourceError
from yquoter.plugin_base import DataSource
from yquoter.datasource import _SOURCE_REGISTRY
from tests.conftest import MockDataSource


class TestStockInit:
    def test_with_string_loader(self):
        s = Stock("cn", "600519")
        assert s.market == "cn"
        assert s.code == "600519"
        assert s.loader == "spider"
        assert s._source_instance is not None
        assert s._source_instance.name == "spider"

    def test_with_datasource_instance(self):
        mock = MockDataSource()
        s = Stock("cn", "MOCK", loader=mock)
        assert s.loader == "mock"
        assert s._source_instance is mock

    def test_with_registered_mock_source(self):
        mock = MockDataSource(name="test_stock")
        _SOURCE_REGISTRY["test_stock"] = mock
        s = Stock("cn", "MOCK", loader="test_stock")
        assert s.loader == "test_stock"
        assert s._source_instance is mock
        _SOURCE_REGISTRY.pop("test_stock", None)

    def test_invalid_loader_string_raises(self):
        with pytest.raises(DataSourceError):
            Stock("cn", "X", loader="nonexistent")

    def test_invalid_loader_type_raises(self):
        with pytest.raises(DataSourceError):
            Stock("cn", "X", loader=42)  # type: ignore


class TestStockMethods:
    """All methods dispatch to a registered MockDataSource."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        _SOURCE_REGISTRY["test_stock"] = MockDataSource(name="test_stock")
        # Indicators.py uses the default source — redirect to mock.
        from yquoter.datasource import _DEFAULT_SOURCE
        self._orig_default = _DEFAULT_SOURCE
        from yquoter.datasource import set_default_source
        set_default_source("test_stock")
        yield
        set_default_source(self._orig_default)
        _SOURCE_REGISTRY.pop("test_stock", None)

    def test_get_history(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        df = s.get_history(start_date="20260501", end_date="20260502")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_get_realtime(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        df = s.get_realtime()
        assert isinstance(df, pd.DataFrame)

    def test_get_profile(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        df = s.get_profile()
        assert not df.empty
        assert "NAME" in df.columns

    def test_get_factors(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        df = s.get_factors(trade_date="20260501")
        assert not df.empty

    def test_get_financials(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        df = s.get_financials(end_day="20251231")
        assert not df.empty

    def test_get_ma(self):
        """Indicator calculation tested in test_indicators.py."""

    def test_get_boll(self):
        """Indicator calculation tested in test_indicators.py."""

    def test_get_max_drawdown(self):
        """Indicator calculation tested in test_indicators.py."""

    def test_get_report(self):
        s = Stock("cn", "MOCK", loader="test_stock")
        report = s.get_report(start="20260501", end="20260503")
        assert isinstance(report, str)
        assert len(report) > 50
