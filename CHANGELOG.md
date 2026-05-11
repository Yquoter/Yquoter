# Changelog

All notable changes to Yquoter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.4.1] — 2026-05-11

### Fixed
- **Cache key source isolation** (P0): cache keys now include the source name,
  preventing cross-source cache poisoning when switching between data sources.
  L2 file paths are prefixed with the source name (`.cache/{source}/{market}/...`).
- **`register_source` accepts DataSource instances**: the function now supports
  both `register_source(name, DataSource())` and the legacy
  `register_source(name, func_type, func)` forms.
- **Indicators respect the plugin system**: all indicator functions now accept
  a `source` parameter and pass it through to the data-fetch layer, so custom
  data sources are used for indicator calculations.
- **MCP Server async dispatch**: data tools now call async dispatch functions
  directly instead of wrapping sync calls in a thread pool, eliminating the
  double async wrapping (async handler → thread pool → asyncio.run_until_complete
  → async spider).
- **Stock resolves source once**: `Stock.__init__` now resolves the data source
  immediately and caches the `DataSource` instance, instead of re-resolving on
  every method call.

### Changed
- MCP Server tools accept an optional `source` parameter for data source selection.
- Updated `examples/plugin_example.py` to use `register_source(name, DataSource())` form.

---

## [0.4.0] — 2026-05-09

### Added
- **MCP Tool layer**: 12 tools via `yquoter[server]` (`mcp>=1.27`)
  - Data query: stock_history, stock_realtime, stock_profile, stock_factors, stock_financials
  - Technical indicators: stock_ma, stock_rsi, stock_bollinger, stock_volatility, stock_max_drawdown
  - AI + report: stock_report, ai_analyze
- Async thread-pool dispatch for spider event-loop safety
- Logging redirected to stderr for clean MCP stdio communication

### Added (previous unreleased items)
- CHANGELOG.md, CONTRIBUTING.md, and plugin developer guide
- Full type annotations across modules (97.8% coverage)

---

## [0.3.3] — 2026-05-09

### Added
- **Test infrastructure**: 93 pytest tests across 7 test files, all
  network-independent (MockDataSource pattern)
- **CI pipeline**: pytest + coverage alongside flake8 in GitHub Actions
- **Plugin discovery**: ``discover_plugins()`` via ``importlib.metadata``
  ``entry_points``; auto-registers third-party DataSources on import
- **Spider entry point**: ``pyproject.toml`` declares ``spider`` plugin

### Fixed
- ``calc_indicator()`` in ``indicators.py`` now correctly handles
  ``real_start`` when both ``df`` and ``start``/``end`` are provided
- CI workflow order: pytest now runs after ``pip install -e .``

---

## [0.3.2] — 2026-05-08

### Added
- **DataSource plugin architecture**: ``DataSource`` ABC in
  ``plugin_base.py`` with 5 sync + 4 async methods, capability
  properties (``supported_types``, ``supports_batch_realtime``)
- **SpiderDataSource**: wraps all Eastmoney spider functions as a
  DataSource plugin
- **TushareDataSource**: wraps TuShare Pro API as a DataSource plugin
  (history + realtime only)
- **DynamicDataSource**: backward-compatible adapter for legacy
  ``register_source()`` callables
- **Multi-level cache**: L1 in-memory LRU with per-data-type TTL and
  entry limits; L2 file cache with TTL expiry (backward-compatible with
  existing CSV files)
- **Cache for async path**: ``_aget_stock_*`` now share L1+L2 cache,
  making report re-generation 10x faster
- **Thread safety**: all cache operations protected by
  ``threading.Lock``

### Fixed
- ``TushareDataSource.get_history()`` now maps ``trade_date`` to
  ``date`` for Yquoter column standardisation
- ``get_stock_realtime_tushare()``: ``datetime.now()`` → ``datetime.datetime.now()``
- ``reporting.py`` async path: ``source`` parameter now correctly
  forwarded to ``asyncio.gather`` calls (was silently ignored)
- Built-in source override protection: ``register_source("spider", ...)``
  creates ``spider_custom`` instead of modifying the built-in source

---

## [0.3.1] — 2025-??

### Added
- **Async concurrent architecture**: ``asyncio.gather`` for report
  generation (up to 2.5x speedup)
- **LLM Gateway**: multi-provider AI analysis supporting DeepSeek,
  OpenAI, Claude, Qwen, Kimi, Gemini with automatic fallback
- **Multi-market support**: unified interface for CN, HK, US
- ``Stock.get_report(language, llm_provider)`` for AI-powered reports

---

## [0.3.0] — 2025-??

### Added
- **Object-oriented design**: ``Stock`` class as primary API
- Chained-style API: ``Stock("cn", "600519").get_history()``
- Backward-compatibility wrappers in ``compat.py`` (deprecated)

---

## [0.2.0] — 2025-??

### Added
- Technical indicators (MA, RSI, BOLL, RV, max drawdown, volume ratio)
- File-based LRU cache for K-line history
- ``register_source`` / ``set_default_source`` API
- Tushare integration (optional)

---

## [0.1.0] — 2025

### Added
- Initial release
- Basic stock history fetching
- Eastmoney spider data source
- CN market support
