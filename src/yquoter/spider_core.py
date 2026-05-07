# yquoter/spider_core.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import asyncio
import threading
import httpx
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from yquoter.logger import get_logger

logger = get_logger(__name__)


# ======================================================================
# Async infrastructure (thread-local event loops)
# ======================================================================
#
# Each thread gets its OWN event loop + httpx client + semaphore.
# This is essential because sync wrappers call ``loop.run_until_complete``,
# which cannot run when another coroutine is executing on the same loop.
# When a caller (e.g. ``reporting.py``) uses a thread pool to fire
# multiple ``_get_stock_*`` calls concurrently, each thread needs an
# independent event loop.
# ======================================================================

_LOCAL = threading.local()

_ASYNC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://quote.eastmoney.com/",
}


async def _async_init_semaphore() -> asyncio.Semaphore:
    """Create the concurrency limiter inside the event loop."""
    return asyncio.Semaphore(2)


def _ensure_event_loop() -> Tuple[
    asyncio.AbstractEventLoop, httpx.AsyncClient, asyncio.Semaphore
]:
    """Get or create the **per-thread** event loop and async client.

    - When called from **sync code** (no running loop), creates a fresh
      thread-local loop + client + semaphore.
    - When called from **async code** (inside a running loop), reuses the
      running loop and lazily creates client / semaphore if missing.

    Each thread gets its own :class:`httpx.AsyncClient` (connection pool)
    and :class:`asyncio.Semaphore` so that multiple threads can safely
    call ``run_until_complete()`` concurrently.

    Returns:
        Tuple of (event_loop, async_client, semaphore).
    """
    loop: asyncio.AbstractEventLoop = getattr(_LOCAL, "loop", None)
    if loop is not None and not loop.is_closed():
        # Fast path: already initialised for this thread
        return _LOCAL.loop, _LOCAL.client, _LOCAL.semaphore

    # Check if we are inside an already-running event loop
    try:
        running = asyncio.get_running_loop()
        # Inside async context – use the running loop
        _LOCAL.loop = running
        _LOCAL.client = httpx.AsyncClient(timeout=30.0)
        # Create Semaphore directly (this is sync-accessible)
        _LOCAL.semaphore = asyncio.Semaphore(2)
        return _LOCAL.loop, _LOCAL.client, _LOCAL.semaphore
    except RuntimeError:
        pass  # No running loop – proceed to create a new one

    # Sync code: create a brand-new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _LOCAL.loop = loop
    _LOCAL.client = httpx.AsyncClient(timeout=30.0)
    _LOCAL.semaphore = loop.run_until_complete(_async_init_semaphore())
    return _LOCAL.loop, _LOCAL.client, _LOCAL.semaphore


def _run_async(coro):
    """Bridge: run an async coroutine from a synchronous context.

    Each thread uses its own persistent event loop (via
    :func:`_ensure_event_loop`), so this function is thread-safe.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The return value of the coroutine.
    """
    loop, _, _ = _ensure_event_loop()
    return loop.run_until_complete(coro)


# ======================================================================
# Sync front-ends (same public API, behaviour preserved)
# ======================================================================


def crawl_kline_segments(
    start_date: str,
    end_date: str,
    make_url: Callable[[str, str], str],
    parse_kline: Callable[[Dict], List[List[str]]],
    sleep_seconds: float = 1.03,
    segment_days: int = 365,
) -> pd.DataFrame:
    """K-line data fetcher (sync front-end).

    Delegates to the concurrent async implementation so that multiple
    time segments are fetched in parallel.

    Args:
        start_date: Start date in ``YYYYMMDD`` format.
        end_date: End date in ``YYYYMMDD`` format.
        make_url: Function ``(beg, end) -> URL`` for a single segment.
        parse_kline: Function ``(json_dict) -> 2D list of rows``.
        sleep_seconds: Post-request delay for anti-crawling.
        segment_days: Days per time segment (default 365).

    Returns:
        pd.DataFrame: OHLCV K-line data.
    """
    return _run_async(
        _async_crawl_kline_segments(
            start_date, end_date, make_url, parse_kline,
            sleep_seconds, segment_days,
        )
    )


def crawl_realtime_data(
    make_url: Callable[[], str],
    parse_realtime_data: Callable[[Dict], List[List[str]]],
    url_fields: List[str],
    user_fields: List[str],
) -> pd.DataFrame:
    """Real-time quote fetcher (sync front-end).

    Delegates to the async implementation.

    Args:
        make_url: Function ``() -> URL``.
        parse_realtime_data: Function ``(json_dict) -> 2D list``.
        url_fields: Column names matching raw API output order.
        user_fields: Final column names required by caller.

    Returns:
        pd.DataFrame: Real-time market data.
    """
    return _run_async(
        _async_crawl_realtime_data(
            make_url, parse_realtime_data, url_fields, user_fields,
        )
    )


def crawl_structured_data(
    make_url: Callable[[], str],
    parse_data: Callable[[Dict], List[List]],
    final_columns: List[str],
    datasource: str,
    sleep_seconds: float = 0.5,
) -> pd.DataFrame:
    """Structured data fetcher (sync front-end).

    Delegates to the async implementation.

    Args:
        make_url: Function ``() -> URL``.
        parse_data: Function ``(json_dict) -> 2D list``.
        final_columns: Output DataFrame column names.
        datasource: Data source name for headers (e.g. ``"eastmoney"``).
        sleep_seconds: Pre-request delay for rate limiting.

    Returns:
        pd.DataFrame: Structured data.
    """
    return _run_async(
        _async_crawl_structured_data(
            make_url, parse_data, final_columns, datasource, sleep_seconds,
        )
    )


def _get_request_headers(datasource: str) -> Dict[str, str]:
    """Return HTTP headers appropriate for a given data source.

    Args:
        datasource: Source name (e.g. ``"eastmoney"``, ``"xueqiu"``).

    Returns:
        Dict[str, str]: HTTP headers.
    """
    base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    ds = datasource.lower()
    ref_map = {
        "eastmoney": "https://quote.eastmoney.com/",
        "xueqiu": "https://xueqiu.com/",
        "sina": "https://finance.sina.com.cn/",
    }
    ref = ref_map.get(ds)
    if ref:
        base["Referer"] = ref
    return base


# ======================================================================
# Async implementations (public, importable directly when needed)
# ======================================================================


async def _async_crawl_kline_segments(
    start_date: str,
    end_date: str,
    make_url: Callable[[str, str], str],
    parse_kline: Callable[[Dict], List[List[str]]],
    sleep_seconds: float = 1.03,
    segment_days: int = 365,
) -> pd.DataFrame:
    """Async implementation: all time segments fetched concurrently.

    Uses a global :class:`httpx.AsyncClient` and an
    :class:`asyncio.Semaphore` (max 2 concurrent requests) to avoid
    triggering anti-crawling measures while maximising throughput.

    Returns:
        pd.DataFrame: K-line data with standard column names.
    """
    # Build segment boundaries
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    segments: List[Tuple[str, str]] = []
    cur = start_dt
    while cur <= end_dt:
        seg_end = min(cur + timedelta(days=segment_days), end_dt)
        segments.append((cur.strftime("%Y%m%d"), seg_end.strftime("%Y%m%d")))
        cur = seg_end + timedelta(days=1)

    _, client, semaphore = _ensure_event_loop()

    async def _fetch_one(beg: str, end: str) -> List[List[str]]:
        try:
            async with semaphore:
                url = make_url(beg, end)
                resp = await client.get(url, headers=_ASYNC_HEADERS)
                resp.raise_for_status()
                rows = parse_kline(resp.json())
                if rows:
                    logger.info(
                        "Fetched segment %s-%s: %d rows", beg, end, len(rows)
                    )
                await asyncio.sleep(sleep_seconds)
                return rows or []
        except Exception as e:
            logger.exception("Segment _fetch_one failed")
            raise

    tasks = [_fetch_one(beg, end) for beg, end in segments]
    all_segments = await asyncio.gather(*tasks, return_exceptions=True)

    all_data: List[List[str]] = []
    for result in all_segments:
        if isinstance(result, Exception):
            logger.error("Segment fetch failed: %s", result)
            continue
        all_data.extend(result)

    if not all_data:
        logger.warning("K-line async crawl completed with no data")
        return pd.DataFrame()

    df = pd.DataFrame(
        all_data,
        columns=[
            "date", "open", "high", "low", "close",
            "vol", "amount", "change%", "turnover%",
            "change", "amplitude%",
        ],
    )
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    logger.info(
        "K-line async crawl completed. Total records: %d", len(all_data)
    )
    return df


async def _async_crawl_realtime_data(
    make_url: Callable[[], str],
    parse_realtime_data: Callable[[Dict], List[List[str]]],
    url_fields: List[str],
    user_fields: List[str],
) -> pd.DataFrame:
    """Async implementation: fetch real-time quotes.

    Returns:
        pd.DataFrame: Real-time data with user-specified columns.
    """
    from yquoter.config import EASTMONEY_REALTIME_MAPPING

    _, client, semaphore = _ensure_event_loop()

    rows: List[List[str]] = []
    logger.info("Starting async real-time data crawl")

    url = make_url()
    try:
        async with semaphore:
            resp = await client.get(url, headers=_ASYNC_HEADERS)
            resp.raise_for_status()
            parsed = parse_realtime_data(resp.json())
            if parsed:
                rows = parsed
                logger.info(
                    "Fetched %d records of real-time data", len(rows)
                )
            else:
                logger.warning("No real-time data available")
    except Exception as e:
        logger.error("Error fetching real-time data: %s", e)

    if not rows:
        logger.warning("Real-time data async crawl completed with no data")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=url_fields)
    df.rename(columns=EASTMONEY_REALTIME_MAPPING, inplace=True)
    df = df[user_fields]
    logger.info("Real-time data async crawl completed successfully")
    return df


async def _async_crawl_structured_data(
    make_url: Callable[[], str],
    parse_data: Callable[[Dict], List[List]],
    final_columns: List[str],
    datasource: str,
    sleep_seconds: float = 0.5,
) -> pd.DataFrame:
    """Async implementation: fetch non-time-series structured data.

    Handles financials, profiles, and factor data.

    Returns:
        pd.DataFrame: Structured data with ``final_columns``.
    """
    _, client, semaphore = _ensure_event_loop()
    headers = _get_request_headers(datasource)
    all_data: List[List] = []

    await asyncio.sleep(sleep_seconds)
    url = make_url()
    logger.info(
        "Starting async structured data crawl from %s ...", datasource
    )

    try:
        async with semaphore:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            rows = parse_data(resp.json())

        if rows:
            all_data.extend(rows)
            logger.info(
                "Successfully fetched structured data, total %d row(s)",
                len(rows),
            )
        else:
            logger.warning("No structured data found in the response")

    except httpx.HTTPStatusError as e:
        logger.error("HTTP Error from %s: %s", datasource, e)
    except Exception as e:
        logger.error(
            "Request/Parsing error for structured data from %s: %s",
            datasource, e,
        )

    if not all_data:
        logger.warning(
            "Structured data async crawl from %s completed with no data",
            datasource,
        )
        return pd.DataFrame(columns=final_columns)

    df = pd.DataFrame(all_data, columns=final_columns)

    for col in df.columns:
        # Only convert object/string columns that look numeric
        if df[col].dtype == object:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().any():
                df[col] = converted

    logger.info(
        "Structured data async crawl from %s completed. Total records: %d",
        datasource, len(all_data),
    )
    return df