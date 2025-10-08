# Yquoter

Yquoter: Your **universal cross-market quote fetcher**. Fetch **A-shares, H-shares, and US stock prices** easily via one interface.

- [![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)
- [![License](https://img.shields.io/github/license/Yodeesy/Yquoter?style=flat)](./LICENSE)

![Yquoter Social Banner](assets/yquoter_banner.png)
---
## 📂 Project Structure
This is a high-level overview of the Yquoter package structure:
```
yquoter/
├── yquoter/
│   ├── __init__.py             # Exposes the main API interfaces (e.g., get_quotes)
│   ├── datasource.py           # Unified interface for all data fetching sources
│   ├── tushare_source.py       # Encapsulates the raw implementation of Tushare
│   ├── spider_source.py        # Fallback data source using internal web scraping
│   ├── spider_core.py          # Core logic and mechanism for the internal spider
│   ├── config.py               # Manages configuration settings (tokens, paths)
│   ├── .env                    # Stores sensitive environment variables (e.g., Tushare token)
│   ├── indicators.py           # Utility for calculating technical indicators
│   ├── logger.py               # Logging configuration and utilities
│   ├── cache.py                # Manages local data caching mechanisms
│   ├── utils.py                # General-purpose utility functions
│   └── configs/
│       ├── mapping.yaml        # Mapping for Data & configs
│       └── standard.yaml       # Yquoter's data standard
│
├── examples/
│   └── basic_usage.ipynb # Detailed usage examples in Jupyter Notebook
│
├── assets/               # Non-code assets (e.g., logos, screenshots for README)
├── temp/                 # Temporary files (ignored by Git)
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

**Returns**: `pandas.DataFrame`

### Data Acquisition Functions

| Function               | Description                                                  | Primary Parameters                         | Returns                       |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------ | ----------------------------- |
| `get_stock_history`    | Fetch historical **OHLCV** (K-line) data for a date range.   | `market`, `code`, `start`, `end`           | `DataFrame` (OHLCV)           |
| `get_stock_realtime`   | Fetch the **latest trading snapshot** (real-time quotes).    | `market`, `codes`                          | `DataFrame` (Realtime Quotes) |
| `get_stock_factors`    | Fetch historical **valuation/market factors** (e.g., PE, PB, Market Cap). | `market`, `code`, `trade_day`              | `DataFrame` (Factors)         |
| `get_stock_profile`    | Fetch **basic profile information** (e.g., company name, listing date, industry). | `market`, `code`                           | `DataFrame` (Profile)         |
| `get_stock_financials` | Fetch **fundamental financial statements** (e.g., Income Statement, Balance Sheet). | `market`, `code`, `end_day`, `report_type` | `DataFrame` (Financials)      |

### Technical Analysis Functions

These functions primarily take an existing DataFrame (`df`) or data request parameters (`market`, `code`, `start`, `end`) and calculate indicators.

| Function           | Description                                                  | Primary Parameters     | Returns                               |
| ------------------ | ------------------------------------------------------------ | ---------------------- | ------------------------------------- |
| `get_ma_n`         | Calculate **N-period Moving Average** (MA).                  | `df`, `n` (default 5)  | `DataFrame` (MA column)               |
| `get_boll_n`       | Calculate **N-period Bollinger Bands** (BOLL).               | `df`, `n` (default 20) | `DataFrame` (BOLL, Upper/Lower bands) |
| `get_rsi_n`        | Calculate **N-period Relative Strength Index** (RSI).        | `df`, `n` (default 14) | `DataFrame` (RSI column)              |
| `get_rv_n`         | Calculate **N-period Rolling Volatility** (RV).              | `df`, `n` (default 5)  | `DataFrame` (RV column)               |
| `get_max_drawdown` | Calculate **Maximum Drawdown** over a period.                | `df`                   | `float` (Max Drawdown value)          |
| `get_vol_ratio`    | Calculate **Volume Ratio** (Volume to its N-period average). | `df`, `n` (default 5)  | `DataFrame` (Volume Ratio)            |

### Utility Functions

| Function                  | Description                                                  | Primary Parameters |
| ------------------------- | ------------------------------------------------------------ |--|
| `init_tushare`            | **Initialize TuShare connection** with your API token.       | `token` |
| `init_cache_manager`      | **Initialize the cache manager** with a maximum LRU entry count. | `max_entries` |
| `register_source`         | **Register** a new custom data **source** plugin.            | `source_name`, `func_type (e.g., "realtime")` |
| `register_tushare_module` | **Register specific `TuShare` data interfaces**. | **None** |
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
