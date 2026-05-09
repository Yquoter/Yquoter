"""Tests for the multi-level cache system (cache.py)."""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from yquoter.cache import (
    _L1Cache,
    make_cache_key,
    cache_get,
    cache_set,
    cache_invalidate,
    get_cache_path,
    save_cache,
    load_cache,
    cache_exists,
    set_max_cache_entries,
    init_cache,
    get_manager,
)


# ======================================================================
# _L1Cache unit tests
# ======================================================================


class TestL1Cache:
    def test_set_get_round_trip(self):
        c = _L1Cache(10, 3600)
        df = pd.DataFrame({"a": [1, 2, 3]})
        c.set(("k",), df)
        result = c.get(("k",))
        assert result is not None
        assert list(result["a"]) == [1, 2, 3]

    def test_get_returns_copy(self):
        c = _L1Cache(10, 3600)
        df = pd.DataFrame({"a": [1, 2, 3]})
        c.set(("k",), df)
        result = c.get(("k",))
        result["a"] = [99, 99, 99]
        original = c.get(("k",))
        assert list(original["a"]) == [1, 2, 3]

    def test_miss_returns_none(self):
        c = _L1Cache(10, 3600)
        assert c.get(("nonexistent",)) is None

    def test_lru_eviction(self):
        c = _L1Cache(3, 3600)
        df = pd.DataFrame({"x": [1]})
        c.set(("a",), df)
        c.set(("b",), df)
        c.set(("c",), df)
        c.get(("a",))  # promote a
        c.set(("d",), df)  # evicts b (LRU)
        assert c.get(("a",)) is not None
        assert c.get(("b",)) is None
        assert c.get(("c",)) is not None
        assert c.get(("d",)) is not None
        assert c.size == 3

    def test_ttl_expiry(self):
        c = _L1Cache(10, 0.05)  # 50 ms TTL
        df = pd.DataFrame({"x": [1]})
        c.set(("k",), df)
        time.sleep(0.06)
        assert c.get(("k",)) is None

    def test_invalidate_single(self):
        c = _L1Cache(10, 3600)
        df = pd.DataFrame({"x": [1]})
        c.set(("k1",), df)
        c.set(("k2",), df)
        c.invalidate(key=("k1",))
        assert c.get(("k1",)) is None
        assert c.get(("k2",)) is not None

    def test_invalidate_all(self):
        c = _L1Cache(10, 3600)
        df = pd.DataFrame({"x": [1]})
        c.set(("a",), df)
        c.set(("b",), df)
        c.invalidate()
        assert c.size == 0

    def test_thread_safety(self):
        c = _L1Cache(50, 3600)
        df = pd.DataFrame({"x": [1]})

        def worker(n):
            for i in range(20):
                key = (f"k{i}",)
                c.set(key, df)
                c.get(key)
                c.invalidate(key=key)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(8)))
        # No crash = pass
        assert c.size <= 50


# ======================================================================
# make_cache_key tests
# ======================================================================


class TestMakeCacheKey:
    def test_history_key(self):
        k = make_cache_key(
            "history", market="cn", code="600519",
            start="20260501", end="20260508", klt="101", fqt="1",
        )
        assert k == ("history", "cn", "600519", "20260501", "20260508", "101", "1")

    def test_profile_key(self):
        k = make_cache_key("profile", market="cn", code="600519")
        assert k == ("profile", "cn", "600519")

    def test_realtime_key_sorted(self):
        k = make_cache_key(
            "realtime", market="cn",
            code=("000001", "600519"),
            fields=("close", "vol"),
        )
        assert k[0] == "realtime"
        assert k[1] == "cn"
        assert k[2] == ("000001", "600519")


# ======================================================================
# Unified cache API tests  (uses l2_cache_dir fixture)
# ======================================================================


class TestCacheAPI:
    def test_cache_set_get_l1_hit(self, l2_cache_dir):
        ckey = make_cache_key("profile", market="cn", code="TEST_UNIFIED")
        df = pd.DataFrame({"NAME": ["test"]})
        cache_set(ckey, "profile", df)
        result = cache_get(ckey, "profile")
        assert result is not None
        assert result.iloc[0]["NAME"] == "test"

    def test_cache_get_miss_returns_none(self, l2_cache_dir):
        result = cache_get(("nonexistent",), "profile")
        assert result is None

    def test_realtime_l1_only(self, l2_cache_dir):
        ckey = make_cache_key("realtime", market="cn", code=("TEST",), fields=())
        df = pd.DataFrame({"close": [100.0]})
        cache_set(ckey, "realtime", df)
        # L1 hit
        result = cache_get(ckey, "realtime")
        assert result is not None
        # No L2 file
        mgr = get_manager()
        path = mgr.get_l2_path("realtime", ckey)
        assert path is None

    def test_cache_invalidate(self, l2_cache_dir):
        ckey = make_cache_key("factors", market="cn", code="INVAL_TEST",
                              trade_date="20260501")
        df = pd.DataFrame({"PE": [15.0]})
        cache_set(ckey, "factors", df)
        assert cache_get(ckey, "factors") is not None
        cache_invalidate("factors", ckey)
        assert cache_get(ckey, "factors") is None

    def test_l2_persistence_and_promotion(self, l2_cache_dir):
        ckey = make_cache_key("profile", market="cn", code="L2_PERSIST")
        mgr = get_manager()
        path = mgr.get_l2_path("profile", ckey)
        assert path is not None

        # Write L2 file directly (simulates previous session).
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df = pd.DataFrame({"NAME": ["persisted"]})
        df.to_csv(path, index=False)

        # Re-init file list.
        init_cache()

        # Should hit L2 and promote to L1.
        result = cache_get(ckey, "profile")
        assert result is not None
        assert result.iloc[0]["NAME"] == "persisted"

        # Second call hits L1.
        result2 = cache_get(ckey, "profile")
        assert result2 is not None

    def test_manager_initialisation_with_overrides(self):
        mgr = get_manager()
        mgr.initialize(
            l1_max_entries={"history": 999},
            l1_ttl={"history": 7200, "profile": 43200},
            l2_ttl={"profile": 999999},
        )
        hc = mgr._l1("history")
        assert hc._max == 999
        assert hc._ttl == 7200
        pc = mgr._l1("profile")
        assert pc._ttl == 43200
        assert mgr._l2_ttl["profile"] == 999999


# ======================================================================
# Legacy API backward compatibility
# ======================================================================


class TestLegacyCacheAPI:
    def test_get_cache_path(self):
        path = get_cache_path("cn", "LEGACY", "20260501", "20260508", 101, 1)
        assert path.endswith("cn/LEGACY/20260501_20260508_klt101_fqt1.csv")

    def test_save_load_round_trip(self, l2_cache_dir):
        path = get_cache_path("cn", "LEGACY2", "20260501", "20260508", 101, 1)
        df = pd.DataFrame({"date": ["20260501"], "close": [100.0]})
        save_cache(path, df)
        assert cache_exists(path)
        loaded = load_cache(path)
        assert loaded is not None
        assert len(loaded) == 1

    def test_set_max_cache_entries(self):
        set_max_cache_entries(100)
        # No crash = pass
        assert True

    def test_legacy_file_loadable_via_new_api(self, l2_cache_dir):
        """Old-format CSV files should be loadable via cache_get."""
        path = get_cache_path("cn", "LEGACY3", "20260501", "20260508", 101, 1)
        df = pd.DataFrame({
            "date": ["20260501", "20260502"],
            "close": [100.0, 101.0],
            "open": [99.0, 100.0],
            "high": [102.0, 103.0],
            "low": [98.0, 99.0],
            "vol": [5000, 6000],
            "amount": [500000, 606000],
        })
        save_cache(path, df)

        ckey = make_cache_key("history", market="cn", code="LEGACY3",
                              start="20260501", end="20260508",
                              klt="101", fqt="1")
        result = cache_get(ckey, "history")
        assert result is not None
        assert len(result) == 2
