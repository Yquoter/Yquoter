# yquoter/mcp_server.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""MCP (Model Context Protocol) server for Yquoter.

Exposes Yquoter's data and analysis capabilities as MCP tools that AI
agents (Claude Desktop, Claude Code, etc.) can discover and invoke.

Usage:
    python -m yquoter.mcp_server

Configure in Claude Desktop::

    {
        "mcpServers": {
            "yquoter": {
                "command": "python",
                "args": ["-m", "yquoter.mcp_server"]
            }
        }
    }
"""

import asyncio
import json
import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from yquoter import Stock

# ---------------------------------------------------------------------------
# Logging: redirect ALL Yquoter log output to stderr so it does not
# interfere with the MCP stdio JSON-RPC protocol (which uses stdout).
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s:%(message)s",
    level=logging.WARNING,
    force=True,
)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Yquoter",
    instructions=(
        "Cross-market financial data & analysis toolkit.  "
        "Supports CN (A-share), HK, and US stocks.  "
        "Use stock_search to look up codes by name or code fragment."
    ),
)

# ---------------------------------------------------------------------------
# Compact column sets (key columns for each data type)
# ---------------------------------------------------------------------------

_COMPACT_HISTORY = [
    "date", "open", "high", "low", "close", "vol", "change%", "turnover%",
]

_COMPACT_REALTIME = [
    "code", "name", "latest", "change%", "vol", "amount",
    "pe", "pb", "total_mv", "circ_mv",
]

_COMPACT_PROFILE = [
    "CODE", "NAME", "INDUSTRY", "MAIN_BUSINESS", "LISTING_DATE",
]

_COMPACT_FACTORS = [
    "TRADE_DATE", "SECURITY_CODE",
    "PE_TTM", "PB_MRQ", "PS_TTM", "PCF_OCF_TTM", "PEG_CAR",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: list | dict | str, **extra) -> str:
    """Wrap a successful response in a consistent envelope."""
    body = {"status": "ok"}
    if isinstance(data, (list, dict)):
        body["data"] = data
    else:
        body["data"] = data
    body.update(extra)
    return json.dumps(body, default=str, ensure_ascii=False)


def _err(e: Exception) -> str:
    return json.dumps({"status": "error", "error": f"{type(e).__name__}: {e}"})


def _compact_df(df, columns: list[str], limit: int = 0):
    """Return a DataFrame subset to *columns* (if they exist), optionally capped."""
    available = [c for c in columns if c in df.columns]
    subset = df[available] if available else df
    if limit and len(subset) > limit:
        subset = subset.head(limit)
    return subset


def _stock(market: str, code: str, source: Optional[str] = None) -> Stock:
    return Stock(market=market, code=code, loader=source)


# ---------------------------------------------------------------------------
# Symbol search (simple static index for CN markets)
# ---------------------------------------------------------------------------

#: A small built-in lookup for common CN stocks.  Agents can use this to
#: resolve company names / partial codes to exact codes.
_STOCK_INDEX: list[dict] = [
    {"code": "600519", "name": "贵州茅台", "market": "cn"},
    {"code": "000858", "name": "五粮液", "market": "cn"},
    {"code": "600036", "name": "招商银行", "market": "cn"},
    {"code": "601318", "name": "中国平安", "market": "cn"},
    {"code": "000333", "name": "美的集团", "market": "cn"},
    {"code": "002415", "name": "海康威视", "market": "cn"},
    {"code": "300750", "name": "宁德时代", "market": "cn"},
    {"code": "600900", "name": "长江电力", "market": "cn"},
    {"code": "601857", "name": "中国石油", "market": "cn"},
    {"code": "600276", "name": "恒瑞医药", "market": "cn"},
    {"code": "000651", "name": "格力电器", "market": "cn"},
    {"code": "002594", "name": "比亚迪", "market": "cn"},
    {"code": "688981", "name": "中芯国际", "market": "cn"},
    {"code": "601166", "name": "兴业银行", "market": "cn"},
    {"code": "600030", "name": "中信证券", "market": "cn"},
    {"code": "000001", "name": "平安银行", "market": "cn"},
    {"code": "601398", "name": "工商银行", "market": "cn"},
    {"code": "601288", "name": "农业银行", "market": "cn"},
    {"code": "600585", "name": "海螺水泥", "market": "cn"},
    {"code": "002714", "name": "牧原股份", "market": "cn"},
    {"code": "603259", "name": "药明康德", "market": "cn"},
    {"code": "601899", "name": "紫金矿业", "market": "cn"},
    {"code": "600809", "name": "山西汾酒", "market": "cn"},
    {"code": "000568", "name": "泸州老窖", "market": "cn"},
    {"code": "300059", "name": "东方财富", "market": "cn"},
    {"code": "688111", "name": "金山办公", "market": "cn"},
    {"code": "600050", "name": "中国联通", "market": "cn"},
    {"code": "00700", "name": "腾讯控股", "market": "hk"},
    {"code": "09988", "name": "阿里巴巴", "market": "hk"},
    {"code": "03690", "name": "美团", "market": "hk"},
    {"code": "09618", "name": "京东集团", "market": "hk"},
    {"code": "01810", "name": "小米集团", "market": "hk"},
    {"code": "AAPL", "name": "Apple Inc.", "market": "us"},
    {"code": "MSFT", "name": "Microsoft Corporation", "market": "us"},
    {"code": "GOOGL", "name": "Alphabet Inc.", "market": "us"},
    {"code": "AMZN", "name": "Amazon.com Inc.", "market": "us"},
    {"code": "NVDA", "name": "NVIDIA Corporation", "market": "us"},
    {"code": "TSLA", "name": "Tesla Inc.", "market": "us"},
    {"code": "META", "name": "Meta Platforms Inc.", "market": "us"},
]


# ======================================================================
# Utility tools
# ======================================================================


@mcp.tool(
    description=(
        "Search for stock codes by name, code fragment, or market.  "
        "Returns matching stocks with their code, name, and market.  "
        "Use this before other tools when the user describes a stock "
        "by name rather than providing an exact code."
    ),
)
async def stock_search(query: str, market: Optional[str] = None) -> str:
    """Look up stock codes by name or code fragment.

    Args:
        query: Company name, partial code, or keyword.  Case-insensitive.
        market: Optional market filter (cn, hk, us).
    """
    q = query.lower().strip()
    results = []
    for entry in _STOCK_INDEX:
        if market and entry["market"] != market.lower():
            continue
        if (q in entry["code"].lower()
                or q in entry["name"].lower()):
            results.append(entry)
    if not results:
        results = [{"hint": f"No matches for '{query}'. Try a code prefix or company name."}]
    return _ok(results, count=len(results))


@mcp.tool(
    description=(
        "Get the data source status and available providers.  "
        "Useful for diagnosing configuration issues."
    ),
)
async def yquoter_status() -> str:
    """Report Yquoter configuration status."""
    from yquoter import get_llm_gateway
    from yquoter.datasource import _SOURCE_REGISTRY, _DEFAULT_SOURCE

    gw = await asyncio.to_thread(get_llm_gateway)
    return _ok({
        "default_source": _DEFAULT_SOURCE,
        "available_sources": list(_SOURCE_REGISTRY.keys()),
        "llm_available": gw.is_available(),
        "llm_providers": list(gw.list_providers()) if gw.is_available() else [],
    })


# ======================================================================
# Data query tools
# ======================================================================


@mcp.tool(
    description=(
        "Fetch historical OHLCV K-line data for a stock.  "
        "Supports CN (A-share), HK, US markets.  "
        "klt: 101=daily, 102=weekly, 103=monthly.  "
        "Set compact=true to return only key columns (date/open/high/low/close/vol).  "
        "Set limit to cap the number of returned rows.  "
        "source: data source name (defaults to the global default, typically 'spider')."
    ),
)
async def stock_history(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    klt: int = 101,
    compact: bool = True,
    limit: int = 0,
    source: Optional[str] = None,
) -> str:
    """Fetch historical K-line data."""
    try:
        from yquoter.datasource import _aget_stock_history

        df = await _aget_stock_history(
            market, code, start=start_date, end=end_date, klt=klt, source=source,
        )
        total = len(df) if df is not None else 0
        if df is None or df.empty:
            return _ok([], total=0, hint="No history data returned.")
        if compact:
            df = _compact_df(df, _COMPACT_HISTORY, limit)
        elif limit:
            df = df.head(limit)
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=total, returned=len(records))
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Fetch real-time quotes for a single stock.  "
        "code is a single symbol like '600519'.  "
        "Set compact=true (default) to return only key fields.  "
        "Use stock_realtime_batch for multiple codes.  "
        "source: data source name (defaults to global default)."
    ),
)
async def stock_realtime(
    market: str,
    code: str,
    compact: bool = True,
    source: Optional[str] = None,
) -> str:
    """Fetch real-time quotes for a single stock."""
    try:
        from yquoter.datasource import _aget_stock_realtime

        df = await _aget_stock_realtime(market, code, source=source)
        if df is None or df.empty:
            return _ok([], total=0, hint="No data returned; market may be closed or code invalid.")
        if compact:
            df = _compact_df(df, _COMPACT_REALTIME)
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=len(records))
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Fetch real-time quotes for multiple stocks at once.  "
        "codes is a comma-separated list like '600519,000858,00700'.  "
        "Much faster than calling stock_realtime individually.  "
        "Set compact=true (default) to return only key fields."
    ),
)
async def stock_realtime_batch(
    market: str,
    codes: str,
    compact: bool = True,
) -> str:
    """Fetch real-time quotes for multiple stocks."""
    try:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        if not code_list:
            return _err(ValueError("No valid codes provided."))
        from yquoter.spider_source import async_get_stock_realtime_spider
        df = await async_get_stock_realtime_spider(market, code_list)
        if df is None or df.empty:
            return _ok([], total=0, hint="No data returned; market may be closed or codes invalid.")
        if compact:
            df = _compact_df(df, _COMPACT_REALTIME)
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=len(records))
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Fetch company profile: name, industry, listing date, business description.  "
        "source: data source name (defaults to global default)."
    ),
)
async def stock_profile(
    market: str, code: str, source: Optional[str] = None,
) -> str:
    """Fetch company profile information."""
    try:
        from yquoter.datasource import _aget_stock_profile

        df = await _aget_stock_profile(market, code, source=source)
        if df is None or df.empty:
            return _ok([], total=0, hint="No profile data returned.")
        df = _compact_df(df, _COMPACT_PROFILE)
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records)
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Fetch valuation factors (PE, PB, PS, etc.) for a stock on a given "
        "trading date.  trade_date format: YYYYMMDD or YYYY-MM-DD.  "
        "source: data source name (defaults to global default)."
    ),
)
async def stock_factors(
    market: str,
    code: str,
    trade_date: str,
    compact: bool = True,
    source: Optional[str] = None,
) -> str:
    """Fetch factor data for a specific trading date."""
    try:
        from yquoter.datasource import _aget_stock_factors

        df = await _aget_stock_factors(market, code, trade_date=trade_date, source=source)
        if df is None or df.empty:
            return _ok([], total=0, hint=f"No factor data for {trade_date}. May be a non-trading day.")
        if compact:
            df = _compact_df(df, _COMPACT_FACTORS)
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records)
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Fetch financial statements.  report_type: CWBB (full financials), "
        "LRB (income statement), ZCFZB (balance sheet), XJLLB (cash flow).  "
        "end_day is the latest report period (e.g. '2025-12-31').  "
        "limit controls how many quarters/years to return.  "
        "source: data source name (defaults to global default)."
    ),
)
async def stock_financials(
    market: str,
    code: str,
    end_day: str,
    report_type: str = "LRB",
    limit: int = 4,
    source: Optional[str] = None,
) -> str:
    """Fetch financial statements."""
    try:
        from yquoter.datasource import _aget_stock_financials

        df = await _aget_stock_financials(
            market, code, end_day=end_day, report_type=report_type, limit=limit,
            source=source,
        )
        if df is None or df.empty:
            return _ok([], total=0, hint="No financial data returned.")
        records = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=len(records))
    except Exception as e:
        return _err(e)


# ======================================================================
# Technical indicator tools
# ======================================================================


@mcp.tool(
    description=(
        "Calculate N-period Moving Average.  n is the window size.  "
        "Common n values: 5 (weekly), 20 (monthly), 60 (quarterly), 200 (yearly).  "
        "Set compact=true to return only the most recent rows plus the MA column."
    ),
)
async def stock_ma(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 20,
    limit: int = 10,
) -> str:
    """Calculate moving average."""
    try:
        df = await asyncio.to_thread(
            _stock(market, code).get_ma,
            start_date=start_date, end_date=end_date, n=n,
        )
        total = len(df)
        ma_col = f"MA{n}"
        cols = ["date", "close", ma_col] if ma_col in df.columns else ["date", "close"]
        available = [c for c in cols if c in df.columns]
        subset = df[available].tail(limit) if limit else df[available]
        records = json.loads(subset.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=total, returned=len(records), indicator=f"MA{n}")
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Calculate N-period Relative Strength Index (RSI).  "
        "Common n values: 6 (short-term), 14 (standard).  "
        "RSI > 70 = overbought, RSI < 30 = oversold."
    ),
)
async def stock_rsi(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 14,
    limit: int = 10,
) -> str:
    """Calculate RSI."""
    try:
        df = await asyncio.to_thread(
            _stock(market, code).get_rsi,
            start_date=start_date, end_date=end_date, n=n,
        )
        total = len(df)
        rsi_col = f"RSI{n}"
        cols = ["date", "close", rsi_col] if rsi_col in df.columns else ["date", "close"]
        available = [c for c in cols if c in df.columns]
        subset = df[available].tail(limit) if limit else df[available]
        records = json.loads(subset.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=total, returned=len(records), indicator=f"RSI{n}")
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Calculate N-period Bollinger Bands.  n defaults to 20.  "
        "Returns upper, mid, and lower bands for the most recent rows."
    ),
)
async def stock_bollinger(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 20,
    limit: int = 10,
) -> str:
    """Calculate Bollinger Bands."""
    try:
        df = await asyncio.to_thread(
            _stock(market, code).get_boll,
            start_date=start_date, end_date=end_date, n=n,
        )
        total = len(df)
        band_cols = ["date", "close"]
        band_cols += [c for c in ["upper", "mid", "lower"] if c in df.columns]
        subset = df[band_cols].tail(limit) if limit else df[band_cols]
        records = json.loads(subset.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=total, returned=len(records), indicator=f"BOLL{n}")
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Calculate N-period rolling volatility (annualized standard deviation "
        "of log returns).  n defaults to 20."
    ),
)
async def stock_volatility(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 20,
    limit: int = 10,
) -> str:
    """Calculate rolling volatility."""
    try:
        df = await asyncio.to_thread(
            _stock(market, code).get_rv,
            start_date=start_date, end_date=end_date, n=n,
        )
        total = len(df)
        rv_col = f"RV{n}"
        cols = ["date", "close", rv_col] if rv_col in df.columns else ["date", "close"]
        available = [c for c in cols if c in df.columns]
        subset = df[available].tail(limit) if limit else df[available]
        records = json.loads(subset.to_json(orient="records", date_format="iso", default_handler=str))
        return _ok(records, total=total, returned=len(records), indicator=f"RV{n}")
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Calculate maximum drawdown and recovery metrics.  "
        "Returns peak date/price, trough date/price, drawdown percentage, "
        "and recovery status."
    ),
)
async def stock_max_drawdown(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Calculate maximum drawdown."""
    try:
        result = await asyncio.to_thread(
            _stock(market, code).get_max_drawdown,
            start_date=start_date, end_date=end_date,
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ======================================================================
# AI + Report tools
# ======================================================================


@mcp.tool(
    description=(
        "Generate a comprehensive stock analysis report in Markdown.  "
        "Includes company profile, real-time quote, price chart, "
        "summary statistics, and optional AI-powered analysis.  "
        "language: 'cn' or 'en'.  "
        "Set llm_provider to enable AI analysis (requires API key in env)."
    ),
)
async def stock_report(
    market: str,
    code: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    language: str = "cn",
    llm_provider: Optional[str] = None,
) -> str:
    """Generate a stock analysis report."""
    try:
        report = await asyncio.to_thread(
            _stock(market, code).get_report,
            start=start, end=end, language=language,
            llm_provider=llm_provider,
        )
        return _ok(report, format="markdown")
    except Exception as e:
        return _err(e)


@mcp.tool(
    description=(
        "Send a prompt to an LLM for AI-powered stock analysis.  "
        "Requires at least one LLM provider API key configured (e.g. "
        "DEEPSEEK_API_KEY).  If provider_name is omitted, providers "
        "are tried in priority order with automatic fallback."
    ),
)
async def ai_analyze(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    provider_name: Optional[str] = None,
    temperature: float = 0.3,
) -> str:
    """Run AI analysis via the LLM gateway."""
    try:
        from yquoter import get_llm_gateway

        gateway = await asyncio.to_thread(get_llm_gateway)
        if not gateway.is_available():
            return _err(RuntimeError(
                "No LLM provider configured. Set DEEPSEEK_API_KEY or similar env var."
            ))

        result = await asyncio.to_thread(
            gateway.analyze,
            system_prompt=system_prompt or "You are a financial analyst.",
            user_prompt=user_prompt,
            provider_name=provider_name,
            temperature=temperature,
        )
        return _ok(result or "(empty response)")
    except Exception as e:
        return _err(e)


# ======================================================================
# Entry point
# ======================================================================


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
