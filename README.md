# Yquoter

[![PyPI](https://img.shields.io/pypi/v/yquoter.svg?style=flat&logo=pypi&label=PyPI)](https://pypi.org/project/yquoter/)
[![TestPyPI](https://img.shields.io/badge/TestPyPI-v0.2.0-orange?style=flat&logo=pypi)](https://test.pypi.org/project/yquoter/)
[![Yquoter CI](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml)
![Status: Alpha](https://img.shields.io/badge/status-alpha-red?style=flat)
[![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)
[![License](https://img.shields.io/github/license/Yodeesy/Yquoter?style=flat)](./LICENSE)
![Yquoter Social Banner](assets/yquoter_banner.png)
---
Yquoter: Your **universal cross-market quote fetcher**. Fetch **A-shares, H-shares, and US stock prices** easily via one interface.

> 🧠 **Project Info**
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
pip install yquoter
# If you need tuShare Module, please use:
# pip install yquoter[tushare]
# If you need a data-visualized report, please use:
# pip install yquoter[plotting]
```

---
## 📂 Project Structure
This is a high-level overview of the Yquoter package structure:
```
Yquoter/
├── src/ 
│   └── yquoter/
│       ├── __init__.py             # Exposes the main API interfaces (e.g., get_quotes)
│       ├── reporting.py            # Generate reports for stocks
│       ├── datasource.py           # Unified interface for all data fetching sources
│       ├── tushare_source.py       # A module for Tushare users, requiring activation
│       ├── spider_source.py        # Default data source using internal web scraping
│       ├── spider_core.py          # Core logic and mechanism for the internal spider
│       ├── config.py               # Manages configuration settings (tokens, paths)
│       ├── .env                    # Stores sensitive environment variables (e.g., Tushare token)
│       ├── indicators.py           # Utility for calculating technical indicators
│       ├── logger.py               # Logging configuration and utilities
│       ├── cache.py                # Manages local data caching mechanisms
│       ├── utils.py                # General-purpose utility functions
│       └── configs/
│           ├── mapping.yaml        # Mapping for Data & configs
│           ├── standard.yaml       # Yquoter's data standard
│           └── dictionary.yaml     # Report's standard words
│
├── examples/
│   └── basic_usage.ipynb # Detailed usage examples in Jupyter Notebook
│
├── assets/               # Non-code assets (e.g., logos, screenshots for README)
├── temp/                 # Temporary files for test (ignored by Git)
├── .cache/               # Cache files (ignored by Git)
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

### Data Acquisition Functions

| Function               | Description                                                  | Primary Parameters                        | Returns                       |
| ---------------------- | ------------------------------------------------------------ | ----------------------------------------- | ----------------------------- |
| `get_stock_history`    | Fetch historical **OHLCV** (K-line) data for a date range.   | `market`, `code`, `start`, `end`          | `DataFrame` (OHLCV)           |
| `get_stock_realtime`   | Fetch the **latest trading snapshot** (real-time quotes).    | `market`, `code`                          | `DataFrame` (Realtime Quotes) |
| `get_stock_factors`    | Fetch historical **valuation/market factors** (e.g., PE, PB). | `market`, `code`, `trade_day`             | `DataFrame` (Factors)         |
| `get_stock_profile`    | Fetch **basic profile information** (e.g., company name, listing date, industry). | `market`, `code`                          | `DataFrame` (Profile)         |
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
| `register_source`         | **Register** a new custom data **source** plugin.            | `source_name`, `func_type (e.g., "realtime")` |
| `set_default_source` | **Set a new default data source.** | `name` |
| `init_tushare`            | **Initialize `TuShare` connection** with your API token and **register`TuShare` data interfaces**. | `token (or None)` |
| `get_newest_df_path`      | **Get the path** of the newest cached data file.             | **None** |

---

## 🛠️ Usage Example

**[📘 View the Basic Usage Tutorial (Jupyter Notebook)](./examples/basic_usage.ipynb)**

---

## 🤝 Contribution Guide

We welcome contributions of all forms, including bug reports, documentation improvements, feature requests, and code contributions.

Before submitting a Pull Request, please ensure that you:

Adhere to the project's **coding standards**.

Add **necessary test cases** to cover new or modified logic.

Update **relevant documentation** (docstrings, README, or examples).

For major feature changes, please open an Issue first to discuss the idea with the community.

---

## 📜 License
This project is licensed under the **Apache License 2.0**. See the LICENSE file for more details.

---
