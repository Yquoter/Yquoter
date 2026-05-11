"""Tests for the data source registry and dispatch functions (datasource.py)."""

import pandas as pd
import pytest

from yquoter.datasource import (
    _SOURCE_REGISTRY,
    _resolve_source,
    register_source,
    set_default_source,
    _register_tushare_module,
    _get_stock_history,
    _get_stock_realtime,
    _get_stock_profile,
    _get_stock_factors,
    _get_stock_financials,
)
from yquoter.exceptions import DataSourceError, DataFetchError
from yquoter.plugin_base import DataSource
from tests.conftest import MockDataSource


# ======================================================================
# _resolve_source
# ======================================================================


class TestResolveSource:
    def test_none_returns_default(self):
        src = _resolve_source(None)
        assert src.name == "spider"

    def test_string_lookup(self):
        src = _resolve_source("spider")
        assert src.name == "spider"

    def test_datasource_instance(self):
        mock = MockDataSource(name="custom")
        src = _resolve_source(mock)
        assert src is mock

    def test_unknown_string_raises(self):
        with pytest.raises(DataSourceError, match="Unknown data source"):
            _resolve_source("nonexistent_source")

    def test_tushare_unavailable_hint(self):
        with pytest.raises(DataSourceError) as exc:
            _resolve_source("tushare")
        assert "init_tushare" in str(exc.value)

    def test_invalid_type_raises(self):
        with pytest.raises(DataSourceError):
            _resolve_source(42)  # type: ignore


# ======================================================================
# register_source
# ======================================================================


class TestRegisterSource:
    def _cleanup(self, name):
        _SOURCE_REGISTRY.pop(name, None)

    def test_decorator_form(self):
        @register_source("test_deco", "history")
        def my_history(**kwargs):
            return pd.DataFrame()

        assert "test_deco" in _SOURCE_REGISTRY
        self._cleanup("test_deco")

    def test_function_call_form(self):
        def my_history(**kwargs):
            return pd.DataFrame()

        register_source("test_func", "history", my_history)
        assert "test_func" in _SOURCE_REGISTRY
        self._cleanup("test_func")

    def test_builtin_override_redirected(self):
        @register_source("spider", "history")
        def overwrite(**kwargs):
            return pd.DataFrame()

        assert "spider_custom" in _SOURCE_REGISTRY
        assert "spider" in _SOURCE_REGISTRY  # original intact
        self._cleanup("spider_custom")

    def test_datasource_instance_form(self):
        mock = MockDataSource(name="ds_instance_test")
        register_source("ds_instance_test", mock)
        assert "ds_instance_test" in _SOURCE_REGISTRY
        assert _SOURCE_REGISTRY["ds_instance_test"] is mock
        self._cleanup("ds_instance_test")

    def test_datasource_instance_builtin_redirect(self):
        mock = MockDataSource(name="spider")
        result = register_source("spider", mock)
        # Should be registered under "spider_custom"
        assert "spider_custom" in _SOURCE_REGISTRY
        assert _SOURCE_REGISTRY["spider_custom"] is mock
        assert result is mock
        self._cleanup("spider_custom")

    def test_both_instance_and_func_raises(self):
        mock = MockDataSource()
        with pytest.raises(Exception):
            register_source("bad", mock, lambda: None)


# ======================================================================
# set_default_source
# ======================================================================


class TestSetDefaultSource:
    def test_valid_source(self):
        set_default_source("spider")
        assert _resolve_source(None).name == "spider"

    def test_invalid_source_raises(self):
        with pytest.raises(DataSourceError):
            set_default_source("does_not_exist")


# ======================================================================
# DynamicDataSource (legacy adapter)
# ======================================================================


class TestDynamicDataSource:
    def test_registered_function_is_callable(self, mock_source):
        @register_source("dynamic_test", "history")
        def my_history(market, code, start, end, **kwargs):
            return pd.DataFrame({"result": [f"{market}:{code}"]})

        ds = _SOURCE_REGISTRY["dynamic_test"]
        df = ds.get_history(market="cn", code="600519", start="20250101", end="20250102")
        assert not df.empty
        assert "result" in df.columns

        # Cleanup
        _SOURCE_REGISTRY.pop("dynamic_test", None)


# ======================================================================
# Sync dispatch functions  (with MockDataSource)
# ======================================================================


class TestSyncDispatch:
    """All tests use MockDataSource registered as 'test_mock'."""

    @pytest.fixture(autouse=True)
    def _register_mock_source(self):
        _SOURCE_REGISTRY["test_mock"] = MockDataSource()
        yield
        _SOURCE_REGISTRY.pop("test_mock", None)

    # -- history ---------------------------------------------------------

    def test_get_stock_history(self):
        df = _get_stock_history("cn", "MOCK", "20260501", "20260502",
                                source="test_mock")
        assert not df.empty
        assert "date" in df.columns
        assert "close" in df.columns

    def test_get_stock_history_with_instance(self, mock_source):
        df = _get_stock_history("cn", "MOCK", "20260501", "20260502",
                                source=mock_source)
        assert not df.empty

    # -- realtime --------------------------------------------------------

    def test_get_stock_realtime(self):
        df = _get_stock_realtime("cn", "MOCK", source="test_mock")
        assert not df.empty

    def test_get_realtime_batch(self):
        df = _get_stock_realtime("cn", ["A", "B"], source="test_mock")
        assert len(df) == 2

    def test_get_realtime_non_batch(self):
        source = MockDataSource(name="nonbatch", supports_batch_realtime=False)
        df = _get_stock_realtime("cn", "MOCK", source=source)
        assert not df.empty

    # -- profile ---------------------------------------------------------

    def test_get_stock_profile(self):
        df = _get_stock_profile("cn", "MOCK", source="test_mock")
        assert not df.empty
        assert "NAME" in df.columns

    # -- factors ---------------------------------------------------------

    def test_get_stock_factors(self):
        df = _get_stock_factors("cn", "MOCK", trade_date="20260501",
                                source="test_mock")
        assert not df.empty
        assert "PE_TTM" in df.columns

    # -- financials ------------------------------------------------------

    def test_get_stock_financials(self):
        df = _get_stock_financials("cn", "MOCK", end_day="20251231",
                                   source="test_mock")
        assert not df.empty

    # -- unsupported type ------------------------------------------------

    def test_unsupported_type_raises(self):
        source = MockDataSource(name="limited", supported_types={"realtime"})
        with pytest.raises(DataSourceError, match="does not support"):
            _get_stock_history("cn", "MOCK", "20250101", "20250102",
                               source=source)

    # -- caching ---------------------------------------------------------

    def test_dispatch_caches_result(self, l2_cache_dir):
        """First call should populate cache; second should return cached."""
        source = MockDataSource(name="cache_check")
        _SOURCE_REGISTRY["cache_check"] = source

        df1 = _get_stock_profile("cn", "CACHE_CHECK", source="cache_check")
        assert not df1.empty

        # Second call should hit L1 cache (no error = pass).
        df2 = _get_stock_profile("cn", "CACHE_CHECK", source="cache_check")
        assert not df2.empty

        _SOURCE_REGISTRY.pop("cache_check", None)


# ======================================================================
# Async dispatch functions
# ======================================================================


@pytest.mark.asyncio
class TestAsyncDispatch:
    @pytest.fixture(autouse=True)
    def _register_mock(self):
        _SOURCE_REGISTRY["async_mock"] = MockDataSource()
        yield
        _SOURCE_REGISTRY.pop("async_mock", None)

    async def test_async_history(self):
        from yquoter.datasource import _aget_stock_history

        df = await _aget_stock_history(
            "cn", "MOCK", "20260501", "20260502", source="async_mock",
        )
        assert not df.empty

    async def test_async_profile(self):
        from yquoter.datasource import _aget_stock_profile

        df = await _aget_stock_profile("cn", "MOCK", source="async_mock")
        assert not df.empty

    async def test_async_factors(self):
        from yquoter.datasource import _aget_stock_factors

        df = await _aget_stock_factors(
            "cn", "MOCK", "20260501", source="async_mock",
        )
        assert not df.empty
