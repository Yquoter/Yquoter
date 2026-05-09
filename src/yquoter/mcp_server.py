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
        "Supports CN (A-share), HK, and US stocks."
    ),
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(fn, *args, **kwargs):
    """Run a synchronous Yquoter function in a thread pool.

    Yquoter's spider data source uses per-thread event loops internally,
    so it must be called from a thread (not the MCP server's async
    event loop).  This helper ensures thread safety.
    """
    return asyncio.get_running_loop().run_in_executor(
        None, lambda: fn(*args, **kwargs),
    )


def _df_to_json(df) -> str:
    """Convert a pandas DataFrame to a JSON string."""
    if df is None or df.empty:
        return "[]"
    return df.to_json(orient="records", date_format="iso", default_handler=str)


def _stock(market: str, code: str) -> Stock:
    return Stock(market=market, code=code)


def _error(e: Exception) -> str:
    return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ======================================================================
# Data query tools
# ======================================================================


@mcp.tool(
    description=(
        "Fetch historical OHLCV K-line data for a stock.  "
        "Supports markets: cn (China A-share), hk (Hong Kong), us (US).  "
        "klt: 101=daily, 102=weekly, 103=monthly.  "
        "Returns a JSON array of records with date, open, high, low, close, vol, amount."
    ),
)
async def stock_history(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    klt: int = 101,
) -> str:
    """Fetch historical K-line data."""
    try:
        df = await _run(
            _stock(market, code).get_history,
            start_date=start_date, end_date=end_date, klt=klt,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Fetch real-time quotes for one or more stocks.  "
        "code can be a single symbol like '600519' or a comma-separated list.  "
        "Returns a JSON array with latest price, volume, etc."
    ),
)
async def stock_realtime(market: str, code: str) -> str:
    """Fetch real-time market data."""
    try:
        code_list = [c.strip() for c in code.split(",")]
        df = await _run(_stock(market, code_list[0]).get_realtime)
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Fetch company profile information: name, industry, listing date, "
        "and business description.  Returns a JSON array."
    ),
)
async def stock_profile(market: str, code: str) -> str:
    """Fetch company profile."""
    try:
        df = await _run(_stock(market, code).get_profile)
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Fetch valuation factors (PE, PB, etc.) for a stock on a specific "
        "trading date.  trade_date format: YYYYMMDD or YYYY-MM-DD.  "
        "Returns a JSON array with factor metrics."
    ),
)
async def stock_factors(market: str, code: str, trade_date: str) -> str:
    """Fetch factor data for a specific trading date."""
    try:
        df = await _run(
            _stock(market, code).get_factors, trade_date=trade_date,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Fetch financial statements.  report_type: CWBB (consolidated), "
        "LRB (income statement), ZCFZB (balance sheet), XJLLB (cash flow), "
        "YJBB (earnings).  limit controls how many periods to return.  "
        "Returns a JSON array with financial data."
    ),
)
async def stock_financials(
    market: str,
    code: str,
    end_day: str,
    report_type: str = "LRB",
    limit: int = 4,
) -> str:
    """Fetch financial statements."""
    try:
        df = await _run(
            _stock(market, code).get_financials,
            end_day=end_day, report_type=report_type, limit=limit,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


# ======================================================================
# Technical indicator tools
# ======================================================================


@mcp.tool(
    description=(
        "Calculate N-period Moving Average (MA) for a stock.  "
        "n is the window size (default 5).  "
        "Returns a JSON array with an MA{n} column added."
    ),
)
async def stock_ma(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 5,
) -> str:
    """Calculate moving average."""
    try:
        df = await _run(
            _stock(market, code).get_ma,
            start_date=start_date, end_date=end_date, n=n,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Calculate N-period Relative Strength Index (RSI) for a stock.  "
        "n is the window size (default 14).  "
        "Returns a JSON array with an RSI{n} column."
    ),
)
async def stock_rsi(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 14,
) -> str:
    """Calculate RSI."""
    try:
        df = await _run(
            _stock(market, code).get_rsi,
            start_date=start_date, end_date=end_date, n=n,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Calculate N-period Bollinger Bands for a stock.  "
        "n is the standard deviation window (default 20).  "
        "Returns a JSON array with upper, mid, and lower band columns."
    ),
)
async def stock_bollinger(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 20,
) -> str:
    """Calculate Bollinger Bands."""
    try:
        df = await _run(
            _stock(market, code).get_boll,
            start_date=start_date, end_date=end_date, n=n,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Calculate N-period rolling volatility (RV) for a stock.  "
        "n is the rolling window size (default 5).  "
        "Returns a JSON array with an RV{n} column."
    ),
)
async def stock_volatility(
    market: str,
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    n: int = 5,
) -> str:
    """Calculate rolling volatility."""
    try:
        df = await _run(
            _stock(market, code).get_rv,
            start_date=start_date, end_date=end_date, n=n,
        )
        return _df_to_json(df)
    except Exception as e:
        return _error(e)


@mcp.tool(
    description=(
        "Calculate maximum drawdown and recovery metrics for a stock.  "
        "Returns a JSON object with max_drawdown, peak/trough dates and "
        "prices, and recovery information."
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
        result = await _run(
            _stock(market, code).get_max_drawdown,
            start_date=start_date, end_date=end_date,
        )
        return json.dumps(result, default=str)
    except Exception as e:
        return _error(e)


# ======================================================================
# AI + Report tools
# ======================================================================


@mcp.tool(
    description=(
        "Generate a comprehensive stock analysis report in Markdown.  "
        "Includes company profile, real-time quote, price chart, "
        "summary statistics, and optional AI analysis.  "
        "language: 'cn' or 'en'.  "
        "llm_provider: 'deepseek', 'ChatGPT', 'Claude', 'qwen', 'kimi', 'gemini'.  "
        "Returns Markdown text."
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
        return await _run(
            _stock(market, code).get_report,
            start=start, end=end, language=language,
            llm_provider=llm_provider,
        )
    except Exception as e:
        return f"Error generating report: {type(e).__name__}: {e}"


@mcp.tool(
    description=(
        "Direct AI analysis using configured LLM providers.  "
        "Supports DeepSeek, OpenAI, Claude, Qwen, Kimi, Gemini.  "
        "If provider_name is omitted, providers are tried in priority order "
        "with automatic fallback.  Returns the analysis text."
    ),
)
async def ai_analyze(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    provider_name: Optional[str] = None,
    temperature: float = 0.3,
) -> str:
    """Send a prompt to the LLM gateway for AI-powered analysis."""
    try:
        from yquoter import get_llm_gateway

        gateway = await asyncio.to_thread(get_llm_gateway)
        if not gateway.is_available():
            return json.dumps(
                {"error": "No LLM provider configured. Set DEEPSEEK_API_KEY or similar."}
            )

        result = await asyncio.to_thread(
            gateway.analyze,
            system_prompt=system_prompt or "You are a financial analyst.",
            user_prompt=user_prompt,
            provider_name=provider_name,
            temperature=temperature,
        )
        return result or json.dumps({"error": "LLM returned empty response."})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ======================================================================
# Entry point
# ======================================================================


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
