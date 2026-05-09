"""Shared test fixtures for the Yquoter test suite.

All tests are designed to run without network access.  Data source
interactions use :class:`MockDataSource`, and the file cache is
redirected to a temporary directory via ``tmp_path``.
"""

from typing import List, Optional, Set, Union
import os

import pandas as pd
import pytest

from yquoter.plugin_base import DataSource


# ---------------------------------------------------------------------------
# Mock DataSource
# ---------------------------------------------------------------------------


class MockDataSource(DataSource):
    """A DataSource that returns synthetic DataFrames without networking.

    Each method returns a standardised DataFrame whose content is
    determined by the *data_type* parameter passed at construction.
    """

    def __init__(
        self,
        name: str = "mock",
        supported_types: Optional[Set[str]] = None,
        supports_batch_realtime: bool = True,
    ) -> None:
        self._name = name
        self._supported = supported_types or {
            "history", "realtime", "financials", "profile", "factors",
        }
        self._batch_rt = supports_batch_realtime

    # -- identity ---------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_types(self) -> Set[str]:
        return self._supported

    @property
    def supports_batch_realtime(self) -> bool:
        return self._batch_rt

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _history_df() -> pd.DataFrame:
        return pd.DataFrame({
            "date": ["20260501", "20260502", "20260503"],
            "open": [1360.0, 1370.0, 1365.0],
            "high": [1380.0, 1385.0, 1375.0],
            "low":  [1355.0, 1360.0, 1358.0],
            "close": [1375.0, 1365.0, 1370.0],
            "vol": [50000, 45000, 48000],
            "amount": [68750000, 61425000, 65760000],
        })

    @staticmethod
    def _realtime_df(code: Union[str, List[str]] = None) -> pd.DataFrame:
        if isinstance(code, list):
            rows = []
            for c in code:
                rows.append({"code": c, "close": 100.0, "vol": 1000, "datetime": "dummy"})
            return pd.DataFrame(rows)

        base = pd.DataFrame({
            "code": [code or "MOCK"],
            "close": [100.0],
            "vol": [1000],
            "open": [99.0],
            "high": [101.0],
            "low": [98.0],
        })
        return base

    @staticmethod
    def _profile_df() -> pd.DataFrame:
        return pd.DataFrame({
            "CODE": ["MOCK"],
            "NAME": ["Mock Company Ltd."],
            "INDUSTRY": ["Technology"],
            "MAIN_BUSINESS": ["Mocking data for tests"],
            "LISTING_DATE": ["2020-01-01"],
        })

    @staticmethod
    def _factors_df() -> pd.DataFrame:
        return pd.DataFrame({
            "TRADE_DATE": ["20260501"],
            "SECURITY_CODE": ["MOCK"],
            "PE_TTM": [15.0],
            "PB_MRQ": [2.0],
            "PS_TTM": [3.0],
        })

    @staticmethod
    def _financials_df() -> pd.DataFrame:
        return pd.DataFrame({
            "REPORT_DATE": ["20251231"],
            "SECURITY_CODE": ["MOCK"],
            "TOTAL_OPERATE_INCOME": [1000000.0],
        })

    # -- sync API ---------------------------------------------------------

    def get_history(self, market, code, start, end, klt=101, fqt=1, **kwargs):
        return self._history_df()

    def get_realtime(self, market, code, fields=None, **kwargs):
        return self._realtime_df(code)

    def get_profile(self, market, code, **kwargs):
        return self._profile_df()

    def get_factors(self, market, code, trade_date, **kwargs):
        return self._factors_df()

    def get_financials(self, market, code, end_day, report_type="CWBB", limit=12, **kwargs):
        return self._financials_df()

    # -- async API --------------------------------------------------------

    async def get_history_async(self, market, code, start, end, klt=101, fqt=1, **kwargs):
        return self._history_df()

    async def get_realtime_async(self, market, code, fields=None, **kwargs):
        return self._realtime_df(code)

    async def get_profile_async(self, market, code, **kwargs):
        return self._profile_df()

    async def get_factors_async(self, market, code, trade_date, **kwargs):
        return self._factors_df()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_source() -> MockDataSource:
    """A MockDataSource that supports all five function types."""
    return MockDataSource()


@pytest.fixture
def sample_history_df() -> pd.DataFrame:
    """A standard 3-row history DataFrame."""
    return MockDataSource._history_df()


@pytest.fixture
def sample_profile_df() -> pd.DataFrame:
    """A standard 1-row profile DataFrame."""
    return MockDataSource._profile_df()


@pytest.fixture
def sample_factors_df() -> pd.DataFrame:
    """A standard 1-row factors DataFrame."""
    return MockDataSource._factors_df()


@pytest.fixture
def sample_financials_df() -> pd.DataFrame:
    """A standard 1-row financials DataFrame."""
    return MockDataSource._financials_df()


@pytest.fixture
def l2_cache_dir(tmp_path) -> str:
    """A temporary directory used as the L2 cache root.

    The fixture sets the ``CACHE_ROOT`` environment variable so that
    :func:`yquoter.config.get_cache_root` returns the temp directory.
    """
    from yquoter.config import get_cache_root as orig_get_root

    cache_root = str(tmp_path / ".cache")
    os.environ["CACHE_ROOT"] = cache_root
    yield cache_root
    # Restore by deleting the env override (the original default is ".cache")
    os.environ.pop("CACHE_ROOT", None)


@pytest.fixture(autouse=True)
def _reset_cache_manager():
    """Reset the CacheManager singleton before each test.

    This ensures tests don't interfere with each other via shared L1 state.
    """
    mgr = _get_manager_safe()
    if mgr is not None:
        mgr.initialize()


def _get_manager_safe():
    """Get the CacheManager without triggering initialisation."""
    try:
        from yquoter.cache import get_manager
        return get_manager()
    except Exception:
        return None
