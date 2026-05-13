# Yquoter

[![PyPI](https://img.shields.io/pypi/v/yquoter.svg?style=flat&logo=pypi&label=PyPI)](https://pypi.org/project/yquoter/)
[![TestPyPI](https://img.shields.io/badge/TestPyPI-v0.4.2-orange?style=flat&logo=pypi)](https://test.pypi.org/project/yquoter/)
[![Yquoter CI](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml)
![Status: Beta](https://img.shields.io/badge/status-beta-yellow?style=flat)
[![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)
[![License](https://img.shields.io/github/license/Yquoter/Yquoter?style=flat)](./LICENSE)

![Yquoter Social Banner](assets/yquoter_banner.png)

---

> ## Disclaimer
>
> **Yquoter is an open-source financial data tool framework for individual
> developers and learners.**
>
> - **The built-in spider is for personal, educational, non-commercial use only.**
>   It scrapes publicly accessible web interfaces and provides **no warranty**
>   of timeliness, accuracy, completeness, or availability.
> - **This project does NOT purchase, hold, or resell any financial data license.**
>   It is not a substitute for legitimate commercial data channels (Tushare
>   Pro, Wind, Bloomberg, etc.).
> - **The data-source plugin architecture is the core design.** Users are
>   expected to bring their own data sources (paid APIs, internal databases,
>   licensed third-party data) by implementing the
>   [`DataSource` ABC](docs/plugin_guide.md). Yquoter serves only as the
>   unified interface layer.
> - **Use at your own risk.** You are solely responsible for complying with
>   the terms of service of any data source you connect, the legality of the
>   data you use, and any consequences of your investment decisions.
> - This project is **not affiliated with** East Money, Tushare, or any other
>   data platform.

---

## Documentation

- [**Contributing Guide**](CONTRIBUTING.md) — development setup, code style, pull requests
- [**Plugin Development Guide**](docs/plugin_guide.md) — create and publish custom data sources
- [**Changelog**](CHANGELOG.md) — version history and release notes
- [**Parameters Reference**](PARAMETERS.md) — detailed parameter descriptions

---

## Features

Yquoter provides a unified interface for fetching and analyzing financial data
across **CN (A-shares)**, **HK (H-shares)**, and **US** markets.

| Category | Capability |
|:---------|:-----------|
| **Market data** | Historical OHLCV (daily/weekly), real-time quotes, company profiles, valuation factors (PE, PB, PS), financial statements (balance sheet, income statement, cash flow) |
| **Technical indicators** | MA, RSI, Bollinger Bands, rolling volatility, volume ratio, maximum drawdown |
| **AI analysis** | Multi-provider LLM gateway (DeepSeek, OpenAI, Claude, Qwen, Kimi, Gemini) with automatic fallback |
| **Reporting** | Markdown/HTML reports with pluggable chart backends (matplotlib/SVG/Plotly), summary statistics, and optional AI commentary |
| **MCP server** | 15-tool MCP-compatible server for AI agent integration (Claude Desktop, VS Code, custom agents) |
| **Plugin system** | `DataSource` ABC — swap or extend the data backend without touching core code |
| **Caching** | Two-level cache (L1 in-memory LRU + L2 file-based CSV) with per-type TTL and thread safety |

---

## Project Info

| | |
|:--|:--|
| **Version** | 0.4.2 |
| **License** | Apache 2.0 |
| **Lead** | [@Yodeesy](https://github.com/Yodeesy) |
| **Contributors** | [@Sukice](https://github.com/Sukice), [@encounter666741](https://github.com/encounter666741), [@Gaeulczy](https://github.com/Gaeulczy) |

Yquoter is developed by the **Yquoter Team**, co-founded by four students from
SYSU and SCUT. The first version (v0.1.0) was completed collaboratively in 2025.

---

## Installation

```bash
pip install yquoter            # Core: spider + caching + indicators + reporting
pip install yquoter[tushare]   # Add Tushare data source (requires token)
pip install yquoter[chart]     # Add K-line chart rendering (matplotlib + mplfinance)
pip install yquoter[plotly]    # Add interactive Plotly chart rendering
pip install yquoter[server]    # Add MCP server (yquoter-server command)
pip install yquoter[all]       # All of the above — full production install
pip install yquoter[dev]       # Development tools (pytest, pytest-cov, pytest-asyncio)
```

---

## Quick Start

```python
from yquoter import Stock

# Create a stock object (default: spider data source)
s = Stock("cn", "600519")

# Fetch data
history   = s.get_history(start_date="2026-01-01", end_date="2026-05-10")
realtime  = s.get_realtime()
profile   = s.get_profile()
factors   = s.get_factors(trade_date="2026-05-09")
financials = s.get_financials(end_day="2025-12-31")

# Technical indicators
ma    = s.get_ma(n=20)
rsi   = s.get_rsi(n=14)
boll  = s.get_boll(n=20)

# Generate a full Markdown report (default)
report = s.get_report(start="2026-01-01", end="2026-05-10", language="en")

# HTML report with interactive Plotly chart
from yquoter import ReportConfig
report = s.get_report(
    start="2026-01-01", end="2026-05-10",
    config=ReportConfig(output_format="html", chart_backend="plotly"),
)

# With AI analysis (requires DEEPSEEK_API_KEY or similar env var)
report = s.get_report(language="en", llm_provider="deepseek")

# Standalone chart rendering
from yquoter import render_chart, prepare_chart_data
df_plot, _ = prepare_chart_data(history, code="600519")
chart = render_chart(df_plot, "600519", backend="svg", fmt="markdown")
```

**[📘 Full tutorial (Jupyter Notebook)](./examples/basic_usage.ipynb)**

---

## Core API

### Stock class (recommended)

The `Stock` class is the primary API. All methods return `pd.DataFrame` unless
noted otherwise.

| Method | Description | Key Parameters |
|:-------|:------------|:---------------|
| `get_history` | Historical OHLCV K-line data | `start_date`, `end_date`, `klt`, `fqt` |
| `get_realtime` | Real-time quote snapshot | `fields` (optional) |
| `get_profile` | Company name, industry, listing date | — |
| `get_factors` | Valuation factors (PE, PB, PS, etc.) | `trade_date` |
| `get_financials` | Financial statements | `end_day`, `report_type`, `limit` |
| `get_ma` | N-period moving average | `start_date`, `end_date`, `n` |
| `get_rsi` | N-period RSI | `start_date`, `end_date`, `n` |
| `get_boll` | N-period Bollinger Bands | `start_date`, `end_date`, `n` |
| `get_rv` | N-period rolling volatility | `start_date`, `end_date`, `n` |
| `get_vol_ratio` | Volume ratio vs. N-period average | `start_date`, `end_date`, `n` |
| `get_max_drawdown` | Max drawdown with recovery metrics | `start_date`, `end_date` |
| `get_report` | Markdown/HTML report with optional AI | `start`, `end`, `language`, `llm_provider`, `config` |

For full parameter details, see the [Parameters Reference](./PARAMETERS.md).

### Switching data sources

```python
# Use Tushare (requires TUSHARE_TOKEN)
from yquoter import init_tushare
init_tushare("your_token")

s = Stock("cn", "600519", loader="tushare")

# Use a custom DataSource instance
from yquoter import DataSource

class MySource(DataSource):
    name = "my_source"
    # implement get_history, get_realtime, ...
    ...

s = Stock("cn", "600519", loader=MySource())
```

### Legacy functions (deprecated since v0.3.0)

Module-level `get_stock_history`, `get_stock_realtime`, `get_stock_financials`,
`get_ma_n`, `get_boll_n`, `generate_stock_report`, etc. are still available for
backward compatibility but emit `DeprecationWarning`. Prefer the `Stock` class.

### Utilities

| Function | Description |
|:---------|:------------|
| `init_cache_manager` | Configure L1/L2 cache TTLs and entry limits |
| `register_source` | Register a custom data source plugin |
| `register_renderer` | Register a custom chart renderer |
| `set_default_source` | Change the default data source |
| `init_tushare` | Initialize Tushare with an API token |
| `get_llm_gateway` | Get the LLM gateway instance |
| `ReportConfig` | Dataclass for report output format, chart backend, etc. |
| `render_chart` | Render a candlestick chart with selectable backend |
| `prepare_chart_data` | Preprocess OHLCV data for chart rendering |
| `get_newest_df_path` | Get the path of the newest cached data file |

---

## LLM Gateway

Yquoter includes a multi-provider AI analysis gateway with automatic provider
detection and priority-based fallback. Configure via environment variables:

| Provider | Env Variable | Default Model |
|:---------|:-------------|:--------------|
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Qwen | `QWEN_API_KEY` | `qwen-plus` |
| Kimi | `KIMI_API_KEY` | `moonshot-v1-8k` |
| Claude | `CLAUDE_API_KEY` | `claude-3-5-haiku-latest` |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |

```python
from yquoter import get_llm_gateway

gateway = get_llm_gateway()
print(gateway.is_available())     # True if any key is set
print(gateway.list_providers())   # List active providers

result = gateway.analyze(
    system_prompt="You are a financial analyst.",
    user_prompt="Analyze the recent price trend...",
    provider_name="deepseek",     # optional; auto-fallback if omitted
)
```

---

## Plugin System

The data-source layer is built on the `DataSource` abstract base class. To plug
in a custom data backend, subclass `DataSource` and implement the methods for
the data types you support.

```python
from yquoter import DataSource, Stock, register_source
import pandas as pd

class MySource(DataSource):
    name = "my_source"

    def get_history(self, market, code, start, end, **kwargs) -> pd.DataFrame:
        # Fetch from your own API / database
        ...

    def get_realtime(self, market, code, **kwargs) -> pd.DataFrame:
        ...

# Register and use
register_source("my_source", MySource())
s = Stock("cn", "600519", loader="my_source")
```

See the [Plugin Development Guide](docs/plugin_guide.md) for the full protocol
(async methods, capability flags, entry-point discovery, and publishing).

---

## MCP Server

Yquoter can run as an MCP-compatible server exposing 15 tools to AI agents:

```json
{
  "mcpServers": {
    "yquoter": {
      "command": "python",
      "args": ["-m", "yquoter.mcp_server"]
    }
  }
}
```

```bash
pip install yquoter[server]
python -m yquoter.mcp_server
```

**Tools**: `stock_search`, `yquoter_status`, `stock_history`, `stock_realtime`,
`stock_realtime_batch`, `stock_profile`, `stock_factors`, `stock_financials`,
`stock_ma`, `stock_rsi`, `stock_bollinger`, `stock_volatility`,
`stock_max_drawdown`, `stock_report`, `ai_analyze`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style,
testing requirements, and pull request workflow.

For plugin development, see the [Plugin Development Guide](docs/plugin_guide.md).

---

## License

This project is licensed under the **Apache License 2.0**. See the
[LICENSE](./LICENSE) file for details.
