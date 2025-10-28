# Yquoter

[![PyPI](https://img.shields.io/pypi/v/yquoter.svg?style=flat&logo=pypi&label=PyPI)](https://pypi.org/project/yquoter/)
[![TestPyPI](https://img.shields.io/badge/TestPyPI-v0.3.0-orange?style=flat&logo=pypi)](https://test.pypi.org/project/yquoter/)
[![Yquoter CI](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yodeesy/Yquoter/actions/workflows/ci.yml)
![Status: Alpha](https://img.shields.io/badge/status-alpha-red?style=flat)
[![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)
[![License](https://img.shields.io/github/license/Yodeesy/Yquoter?style=flat)](./LICENSE)

![Yquoter Social Banner](assets/yquoter_banner.png)
---
Yquoter: Your **universal cross-market quote fetcher**. Fetch **A-shares, H-shares, and US stock prices** easily via one interface.

---

## 🌟 Major Update: Object-Oriented API

From v0.3.0, all core operations are now methods of the `Stock` class.  

### 🆕 Object-Oriented Design

```py
# e.g.
from yquoter import Stock

# New chained style
df = Stock("AAPL").get_history(start_date="2023-01-01")
```

### ⚠️ Compatibility Notice

- **Old functions still work** (`get_stock_history`, `get_ma_n`)
- **Deprecated** - will be removed in v1.0.0

---

> 🧠 **Project Info**
>
> - Version: 0.3.0 
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
│       ├── __init__.py             # Exposes the main API interfaces (e.g., get_quotes)
│       ├── reporting.py            # Generate reports for stocks
│       ├── datasource.py           # Unified interface for all data fetching sources
│       ├── tushare_source.py       # A module for Tushare users, requiring activation
│       ├── spider_source.py        # Default data source using internal web scraping
│       ├── spider_core.py          # Core logic and mechanism for the internal spider
│       ├── config.py               # Manages configuration settings (tokens, paths)
│       ├── models.py               # Offer a type-safe and intuitive API
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
| `get_report`       | Generate a visualized report of history, realtime, and profile. | `start_date`, `end_date`, `language`                         | `str` (report file path)              | A powerful new feature that consolidates multiple data points. |

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
