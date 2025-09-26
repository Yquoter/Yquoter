# Yquoter
Yquoter: Your **universal cross-market quote fetcher**. Fetch **A-shares, H-shares, and US stock prices** easily via one interface.
[![Join Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/UpyzsF2Kj4)

![Yquoter Social Banner](assets/yquoter_banner.png)
---
## 📂 Project Structure
This is a high-level overview of the Yquoter package structure:
```
yquoter/
├── yquoter/
│   ├── __init__.py       # Exposes the main API interfaces (e.g., get_quotes)
│   ├── datasource.py     # Unified interface for all data fetching sources
│   ├── tushare_source.py # Encapsulates the raw implementation of Tushare
│   ├── spider_source.py  # Fallback data source using internal web scraping
│   ├── spider_core.py    # Core logic and mechanism for the internal spider
│   ├── config.py         # Manages configuration settings (tokens, paths)
│   ├── .env              # Stores sensitive environment variables (e.g., Tushare token)
│   ├── indicators.py     # Utility for calculating technical indicators
│   ├── logger.py         # Logging configuration and utilities
│   ├── cache.py          # Manages local data caching mechanisms
│   └── utils.py          # General-purpose utility functions
│
├── examples/
│   └── basic_usage.ipynb # Detailed usage examples in Jupyter Notebook
│
├── assets/               # Non-code assets (e.g., logos, screenshots for README)
├── temp/                 # Temporary files (ignored by Git)
├── .cache/               # Cache files (ignored by Git)
├── setup.py              # Package configuration for distribution (PyPI)
├── requirements.txt      # Declaration of project dependencies
├── LICENSE               # Apache 2.0 Open Source License details
├── README.md             # Project documentation (this file)
├── .gitignore            # Files/directories to exclude from version control
└── .github/workflows/ci.yml  # GitHub Actions workflow for Continuous Integration
```
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
