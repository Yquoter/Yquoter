# Contributing to Yquoter

We welcome contributions of all forms: bug reports, documentation
improvements, feature requests, and code contributions.

## Development Setup

```bash
git clone https://github.com/Yquoter/Yquoter && cd Yquoter
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs Yquoter in editable mode with test dependencies.

## Code Style

Yquoter follows **PEP 8** with a 120-character line limit:

```bash
pip install flake8
flake8 src/yquoter --max-line-length=120 --statistics
```

Continuous Integration enforces:

- **E9/F63/F7/F82** (critical errors) — **must pass** (exit code 1)
- **All other flake8 rules** — advisory (exit code 0)

## Type Annotations

All public functions **must** have complete type annotations (parameters
and return type).  Internal helpers should also be annotated where
practical.  This ensures compatibility with future MCP tool generation.

## Testing

Yquoter uses **pytest**.  All tests run without network access.

```bash
pip install pytest pytest-cov
pytest tests/ --cov=src/yquoter --cov-report=term-missing
```

Test requirements:

- Every new feature must include tests.
- Tests must not depend on live APIs (use ``MockDataSource``).
- Run the full suite before submitting a PR; all 93+ tests must pass.

## Data Source Plugins

See [Plugin Development Guide](docs/plugin_guide.md) for detailed
instructions on creating and publishing third-party data sources.

## Pull Request Checklist

1. Branch from ``main``.
2. Implement your change and add tests.
3. Run flake8 and fix any E9/F63/F7/F82 errors.
4. Run pytest and ensure all tests pass.
5. Update documentation (docstrings, README, or examples) as needed.
6. Open a PR with a clear title and description.

## Project Structure

```
src/yquoter/              # Package source
├── plugin_base.py        # DataSource ABC (plugin protocol)
├── datasource.py         # Registry & dispatch
├── spider_source.py      # Eastmoney spider plugin
├── tushare_source.py     # TuShare Pro plugin
├── cache.py              # Multi-level cache (L1 + L2)
├── models.py             # Stock class
├── indicators.py         # Technical indicators
├── reporting.py          # Report generation
├── llm_gateway.py        # LLM analysis gateway
├── config.py             # Configuration
├── compat.py             # Legacy wrappers
├── utils.py / logger.py / exceptions.py
└── configs/              # YAML field mappings

tests/                    # Pytest test suite
├── conftest.py           # MockDataSource + shared fixtures
├── test_cache.py
├── test_plugin_base.py
├── test_datasource.py
├── test_models.py
├── test_indicators.py
├── test_compat.py
└── test_reporting.py

docs/                     # Documentation
└── plugin_guide.md       # Plugin development tutorial
```

## License

By contributing, you agree that your contributions will be licensed
under the Apache License 2.0.
