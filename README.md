# Yquoter

[![PyPI](https://img.shields.io/pypi/v/yquoter.svg?style=flat&logo=pypi&label=PyPI)](https://pypi.org/project/yquoter/)
[![TestPyPI](https://img.shields.io/badge/TestPyPI-v0.3.3-orange?style=flat&logo=pypi)](https://test.pypi.org/project/yquoter/)
[![Yquoter CI](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml)
![Status: Beta](https://img.shields.io/badge/status-beta-yellow?style=flat)
[![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)
[![License](https://img.shields.io/github/license/Yquoter/Yquoter?style=flat)](./LICENSE)

![Yquoter Social Banner](assets/yquoter_banner.png)
---
Yquoter: Your **universal cross-market quote fetcher**. Fetch **A-shares, H-shares, and US stock prices** easily via one interface.

### 📚 Documentation

- [**Contributing Guide**](CONTRIBUTING.md) — development setup, code style, pull requests
- [**Plugin Development Guide**](docs/plugin_guide.md) — create and publish custom data sources
- [**Changelog**](CHANGELOG.md) — version history and release notes
- [**Parameters Reference**](PARAMETERS.md) — detailed parameter descriptions

---

## 🌟 Major Update: v0.3.2 — Plugin Architecture & Multi-Level Cache

### 🏗️ Data Source Plugin System

The data source layer has been refactored into a proper plugin architecture:

- **``DataSource`` Abstract Base Class**: Define sync/async methods for history,
  realtime, profile, factors, and financials.  Third-party sources can be
  added via ``pip install`` with zero changes to core code.
- **``register_source`` / ``set_default_source``**: Fully backward-compatible.
- **Per-Source Capabilities**: Each source declares ``supported_types`` and
  ``supports_batch_realtime`` — the dispatch layer handles the rest.

```py
from yquoter import Stock, DataSource

# Use a built-in source
s = Stock("cn", "600519", loader="tushare")

# Or pass a DataSource instance directly
class MySource(DataSource):
    name = "my_source"
    def get_history(self, ...): ...
s2 = Stock("cn", "600519", loader=MySource())
```

### ⚡ Multi-Level Cache (L1 Memory + L2 File)

Repeated queries are now near-instant:

- **L1 In-Memory Cache**: Per-data-type LRU with TTL.  History (100 entries, 1h),
  profile (20, 24h), factors (20, 1h), financials (10, 24h), realtime (5, 30s).
- **L2 File Cache**: Persisted CSV files with TTL.  Existing cache files
  remain compatible.
- **Unified Path**: Async dispatch (``reporting.py``) now shares the same cache,
  making report re-generation 10x faster.
- **Thread-Safe**: All cache operations protected by per-type ``threading.Lock``.

```py
from yquoter import init_cache_manager

# Customise cache TTLs if desired
init_cache_manager(
    l1_ttl={"history": 1800, "realtime": 15},
    l1_max_entries={"history": 200},
)
```

### 🚀 v0.3.1 Highlights (previous)

- **Async Concurrent Architecture**: Report generation uses ``asyncio.gather``.
- **AI-Powered Analysis**: LLM Gateway with DeepSeek, ChatGPT, Claude, etc.
- **Multi-Market Support**: CN, HK, US via a single interface.

---

> 🧠 **Project Info**
>
> - Version: 0.3.2 
>
> **Yquoter** is developed by the **Yquoter Team**, co-founded by four students from SYSU and SCUT.  
>
> **Project Lead:** [@Yodeesy](https://github.com/Yodeesy)  
> **Core Contributors:** [@Sukice](https://github.com/Sukice), [@encounter666741](https://github.com/encounter666741), [@Gaeulczy](https://github.com/Gaeulczy)  
>
> The first version (v0.1.0) was completed collaboratively in 2025.

---

## 📦 Installation

```bash
## Installation Options
# Minimal:
pip install yquoter
# With Tushare Module
pip install yquoter[tushare]
# With Plotting
pip install yquoter[plotting]
# Full install
pip install yquoter[all]
```

---
## 📂 Project Structure
This is a high-level overview of the Yquoter package structure:
```
Yquoter/
├── src/ 
│   └── yquoter/
│       ├── __init__.py             # Public API exports (Stock, LLMGateway, etc.)
│       ├── plugin_base.py          # DataSource ABC (plugin protocol)
│       ├── reporting.py            # Stock report generation (Markdown + charts)
│       ├── datasource.py           # Data source registry & dispatch layer
│       ├── tushare_source.py       # TuShare data source module (optional)
│       ├── spider_source.py        # Default web-scraping data source
│       ├── spider_core.py          # Async concurrency engine (httpx + asyncio)
│       ├── llm_gateway.py          # AI analysis gateway (multi-provider)
│       ├── llm_prompts.py          # LLM prompt templates for analysis
│       ├── config.py               # Configuration management (env, YAML)
│       ├── models.py               # Stock class (type-safe OOP interface)
│       ├── indicators.py           # Technical indicators (MA, RSI, BOLL, etc.)
│       ├── logger.py               # Logging configuration
│       ├── cache.py                # Multi-level cache (L1 memory + L2 file)
│       ├── utils.py                # General-purpose utilities
│       ├── exceptions.py           # Custom exception classes
│       ├── compat.py               # Backward-compat legacy function wrappers
│       └── configs/
│           ├── mapping.yaml        # API field name mappings
│           ├── standard.yaml       # Data standard definitions
│           └── dictionary.yaml     # Localized report dictionary (CN/EN)
│
├── examples/
│   └── basic_usage.ipynb           # Jupyter Notebook with usage examples
│
├── assets/                         # Non-code assets (logos, banners)
├── out/                            # Generated reports (ignored by Git)
├── .cache/                         # Cache directory (ignored by Git)
├── pyproject.toml        # Package configuration for distribution (PyPI)
├── requirements.txt      # Declaration of project dependencies
├── LICENSE               # Apache 2.0 Open Source License details
├── README.md             # Project documentation (this file)
├── .gitignore            # Files/directories to exclude from version control
└── .github/workflows/ci.yml  # GitHub Actions workflow for Continuous Integration
```
---
## 🚀 Core API Reference

The **Yquoter** library exposes a set of standardized functions for data acquisition and technical analysis.

For detailed descriptions of all function parameters (e.g., market, klt, report_type), please refer to the dedicated **[Parameters Reference](./PARAMETERS.md)**.

> 📝 **Note:** Yquoter internally integrates and standardizes external data sources like **Tushare**. This means Tushare users can leverage Yquoter's unified API and caching mechanisms without dealing with complex native interface calls. To learn more about the underlying data source, visit the [Tushare GitHub repository](https://github.com/waditu/tushare).

**Returns**: `pandas.DataFrame`

### Stock Class Methods Reference (Optimized for O-O)

| unction            | Description                                                  | Primary Parameters                                           | Returns                               | Notes                                                        |
| ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------- | ------------------------------------------------------------ |
| `get_history`      | Fetch historical **OHLCV (K-line)** data for a date range.   | `start_date`, `end_date`, `klt`, `fqt`, `fields('basic' or 'full')` | `DataFrame` (OHLCV)                   | These parameters define the data range and frequency.        |
| `get_realtime`     | Fetch the latest trading snapshot (**real-time quotes**).    | `fields` (optional)                                          | `DataFrame` (Realtime Quotes)         | The stock is determined by the instance's `code`.            |
| `get_factors`      | Fetch historical **valuation/market factors** (e.g., PE, PB). | `trade_date`                                                 | `DataFrame` (Factors)                 | `trade_date` specifies the day for the factor data.          |
| `get_profile`      | Fetch **basic profile information** (company name, listing date, industry). | **None**                                                     | `DataFrame` (Profile)                 | Requires no parameters; uses the object's stored `code`.     |
| `get_financials`   | Fetch fundamental **financial statements** (e.g., Income Statement, Balance Sheet). | `end_day`, `report_type`, `limit`                            | `DataFrame` (Financials)              | `end_day` is the cutoff date for the report.                 |
| `get_ma`           | Calculate **N-period Moving Average (MA)**.                  | `n` (default 5)                                              | `DataFrame` (MA column)               | The calculation is run on the instance's latest history data. |
| `get_boll`         | Calculate **N-period Bollinger Bands (BOLL)**.               | `n` (default 20)                                             | `DataFrame` (BOLL, Upper/Lower bands) | -                                                            |
| `get_rsi`          | Calculate **N-period Relative Strength Index (RSI)**.        | `n` (default 5)                                              | `DataFrame` (RSI column)              | -                                                            |
| `get_rv`           | Calculate **N-period Rolling Volatility (RV)**.              | `n` (default 5)                                              | `DataFrame` (RV column)               | -                                                            |
| `get_max_drawdown` | Calculate **Maximum Drawdown and Recovery** over a period.   | `n` (default 5)                                              | `Dict` (Max Drawdown)                 | Runs on the instance's history or an optionally provided `df`. |
| `get_vol_ratio`    | Calculate **Volume Ratio** (Volume to its N-period average). | `n` (default 20)                                             | `DataFrame` (Volume Ratio)            | -                                                            |
| `get_report`       | Generate a comprehensive Markdown report with profile, realtime, history chart, summary stats, and optional AI analysis. | `start`, `end`, `language`, `llm_provider` (optional) | `str` (Markdown content)              | When ``llm_provider`` is set (e.g. ``"deepseek"``), AI-powered market analysis is appended. |

### Data Acquisition Functions

| Function               | Description                                                  | Primary Parameters                         | Returns                       |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------ | ----------------------------- |
| `get_stock_history`    | Fetch historical **OHLCV** (K-line) data for a date range.   | `market`, `code`, `start`, `end`           | `DataFrame` (OHLCV)           |
| `get_stock_realtime`   | Fetch the **latest trading snapshot** (real-time quotes).    | `market`, `code`                           | `DataFrame` (Realtime Quotes) |
| `get_stock_factors`    | Fetch historical **valuation/market factors** (e.g., PE, PB). | `market`, `code`, `trade_day`              | `DataFrame` (Factors)         |
| `get_stock_profile`    | Fetch **basic profile information** (e.g., company name, listing date, industry). | `market`, `code`                           | `DataFrame` (Profile)         |
| `get_stock_financials` | Fetch **fundamental financial statements** (e.g., Income Statement, Balance Sheet). | `market`, `code`, `end_day`, `report_type` | `DataFrame` (Financials)      |

### Technical Analysis Functions

These functions primarily take an existing DataFrame (`df`) or data request parameters (`market`, `code`, `start`, `end`) and calculate indicators.

| Function           | Description                                                    | Primary Parameters     | Returns                               |
| ------------------ |----------------------------------------------------------------| ---------------------- |---------------------------------------|
| `get_ma_n`         | Calculate **N-period Moving Average** (MA).                    | `df`, `n` (default 5)  | `DataFrame` (MA column)               |
| `get_boll_n`       | Calculate **N-period Bollinger Bands** (BOLL).                 | `df`, `n` (default 20) | `DataFrame` (BOLL, Upper/Lower bands) |
| `get_rsi_n`        | Calculate **N-period Relative Strength Index** (RSI).          | `df`, `n` (default 14) | `DataFrame` (RSI column)              |
| `get_rv_n`         | Calculate **N-period Rolling Volatility** (RV).                | `df`, `n` (default 5)  | `DataFrame` (RV column)               |
| `get_max_drawdown` | Calculate **Maximum Drawdown** and **Recovery** over a period. | `df`                   | `Dict` (Max Drawdown)                 |
| `get_vol_ratio`    | Calculate **Volume Ratio** (Volume to its N-period average).   | `df`, `n` (default 5)  | `DataFrame` (Volume Ratio)            |

### Utility Functions

| Function                  | Description                                                  | Primary Parameters |
| ------------------------- | ------------------------------------------------------------ |--|
| `init_cache_manager`      | **Initialize the cache manager** with a maximum LRU entry count. | `max_entries` |
| `generate_stock_report` | Generate **a visualized report** of **history**, **realtime**, **profile** of a stock. | `market`, `code`, `start_date`, `end_date`, `language('cn' or 'en')` |
| `register_source`         | **Register** a new custom data **source** plugin.            | `source_name`, `func_type (e.g., "realtime")` |
| `set_default_source` | **Set a new default data source.** | `name` |
| `init_tushare`            | **Initialize `TuShare` connection** with your API token and **register`TuShare` data interfaces**. | `token (or None)` |
| `get_newest_df_path`      | **Get the path** of the newest cached data file.             | **None** |

---

## 🤖 LLM Gateway (AI-Powered Analysis)

Yquoter includes a built-in **LLM Gateway** that connects to multiple AI providers
for automated market analysis. It supports automatic provider detection and
priority-based fallback.

### Configured via environment variables

| Provider   | Env Variable       | Default Model          |
|:-----------|:-------------------|:-----------------------|
| DeepSeek   | `DEEPSEEK_API_KEY` | `deepseek-chat`        |
| OpenAI     | `OPENAI_API_KEY`   | `gpt-4o-mini`          |
| Qwen       | `QWEN_API_KEY`     | `qwen-plus`            |
| Kimi       | `KIMI_API_KEY`     | `moonshot-v1-8k`       |
| Claude     | `CLAUDE_API_KEY`   | `claude-3-5-haiku-latest` |
| Gemini     | `GEMINI_API_KEY`   | `gemini-2.0-flash`     |

### Usage

```py
from yquoter import get_llm_gateway

gateway = get_llm_gateway()

# Check if any provider is configured
print(gateway.is_available())  # True / False

# List active providers
print(gateway.list_providers())

# Direct LLM analysis
result = gateway.analyze(
    system_prompt="You are a financial analyst.",
    user_prompt="Analyze the recent price trend...",
    provider_name="deepseek",  # optional; auto-fallback if omitted
)
```

### Use AI in stock reports

```py
from yquoter import Stock

# Generate a report with DeepSeek AI analysis
report = Stock("cn", "600519").get_report(
    language="cn",
    llm_provider="deepseek",
)
# The AI section is appended after the data sections
```

---

## 🛠️ Usage Example

**[📘 View the Basic Usage Tutorial (Jupyter Notebook)](./examples/basic_usage.ipynb)**

---

## 🤝 Contributing

See [**CONTRIBUTING.md**](CONTRIBUTING.md) for development setup, code
style, testing requirements, and pull request workflow.

For plugin development, see the [**Plugin Development Guide**](docs/plugin_guide.md).

---

## 📜 License
This project is licensed under the **Apache License 2.0**. See the LICENSE file for more details.

---
