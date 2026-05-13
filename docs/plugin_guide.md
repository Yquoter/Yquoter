# Plugin Development Guide

This guide walks you through creating a third-party data source plugin
for Yquoter.  By the end you will have a working plugin that can be
published to PyPI and auto-discovered by Yquoter users.

---

## Table of Contents

1. [Overview](#overview)
2. [Minimal Plugin](#minimal-plugin)
3. [Complete Plugin Template](#complete-plugin-template)
4. [Capability Declaration](#capability-declaration)
5. [Async Optimisation](#async-optimisation)
6. [Registration & Discovery](#registration--discovery)
7. [Publishing to PyPI](#publishing-to-pypi)
8. [Testing](#testing)
9. [Chart Renderer Plugins](#chart-renderer-plugins)
   - [Concept](#chart-concept)
   - [ChartRenderer Protocol](#chartrenderer-protocol)
   - [Built-in Renderers](#built-in-renderers)
   - [Render Function](#render-function)
   - [ReportConfig Integration](#reportconfig-integration)
   - [Custom Renderer](#custom-renderer)
   - [Registration & Auto-Resolution](#chart-registration--auto-resolution)

---

## Overview

Every Yquoter data source is a subclass of
:class:`yquoter.plugin_base.DataSource`.  The ABC defines five
synchronous methods (one per data type) and four asynchronous variants:

| Data Type    | Sync method               | Async method                  |
|--------------|---------------------------|-------------------------------|
| History      | ``get_history()``         | ``get_history_async()``       |
| Realtime     | ``get_realtime()``        | ``get_realtime_async()``      |
| Profile      | ``get_profile()``         | ``get_profile_async()``       |
| Factors      | ``get_factors()``         | ``get_factors_async()``       |
| Financials   | ``get_financials()``      | ``get_financials_async()``    |

You only need to implement the methods your source supports.  Unsupported
methods raise :class:`~yquoter.exceptions.DataSourceError` by default.

---

## Minimal Plugin

A plugin that only provides historical data:

```python
import pandas as pd
from yquoter.plugin_base import DataSource


class MySimpleSource(DataSource):

    name = "my_simple"
    supported_types = {"history"}

    def get_history(self, market, code, start, end, klt=101, fqt=1, **kwargs):
        # Fetch data from your API ...
        return pd.DataFrame({
            "date": [start, end],
            "open":  [100.0, 101.0],
            "close": [100.5, 101.5],
            "high":  [102.0, 103.0],
            "low":   [99.0,  100.0],
            "vol":   [1000,  1200],
            "amount": [100500, 121800],
        })
```

Users can pass your source directly:

```python
from yquoter import Stock
s = Stock("us", "AAPL", loader=MySimpleSource())
df = s.get_history(start_date="2025-01-01")
```

---

## Complete Plugin Template

```python
from typing import List, Optional, Set, Union

import pandas as pd

from yquoter.plugin_base import DataSource


class MyDataSource(DataSource):
    """My custom data source.

    Provides history and realtime data for CN markets.
    """

    # -- Identity --

    name = "my_source"

    # -- Capabilities --

    supported_types = {"history", "realtime"}

    @property
    def supports_batch_realtime(self) -> bool:
        """Return ``True`` if get_realtime() accepts a list of codes."""
        return True

    # -- History --

    def get_history(
        self,
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int = 101,
        fqt: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        # Your API call here.
        return pd.DataFrame(...)

    # -- Realtime --

    def get_realtime(
        self,
        market: str,
        code: Union[str, List[str]],
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        # ``code`` is a ``List[str]`` when ``supports_batch_realtime``
        # is ``True``, or a single ``str`` when ``False``.
        return pd.DataFrame(...)

    # -- Profile (optional) --

    def get_profile(
        self,
        market: str,
        code: str,
        **kwargs,
    ) -> pd.DataFrame:
        raise DataSourceError(f"'{self.name}' does not support profile data.")
```

---

## Capability Declaration

### ``supported_types``

A :class:`set` of strings declaring what data types your source provides:

```python
supported_types = {"history", "realtime"}
```

Valid values: ``"history"``, ``"realtime"``, ``"profile"``,
``"factors"``, ``"financials"``.

If a user requests an unsupported type, the dispatch layer raises a
helpful ``DataSourceError`` before calling your code.

### ``supports_batch_realtime``

Controls how the dispatch layer calls ``get_realtime()``:

- **``True`` (default)**: ``code`` is ``List[str]`` — you receive all
  codes in a single call.  Suitable for APIs with batch endpoints.
- **``False``**: the dispatch layer iterates codes one by one and calls
  ``get_realtime(code=str)`` each time.  Required for APIs like TuShare
  that accept only one code per request.

---

## Async Optimisation

The ``DataSource`` ABC provides default async implementations that wrap
the sync method in a thread-pool executor.  This works for any source
without extra code.

For sources with native async support (e.g. ``httpx.AsyncClient``),
override the async method directly:

```python
class FastSource(DataSource):
    name = "fast"
    supported_types = {"history"}

    async def get_history_async(
        self, market, code, start, end, **kwargs,
    ) -> pd.DataFrame:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.example.com/{code}")
            return pd.DataFrame(resp.json())
```

When a native async override exists, the dispatch layer uses it.  When
not, the thread-pool fallback is used transparently.

---

## Registration & Discovery

### Entry Points (Automatic)

The recommended approach.  Add to your ``pyproject.toml``:

```toml
[project.entry-points."yquoter.data_sources"]
my_source = "my_package.my_module:MyDataSource"
```

Users install your package with ``pip`` and the source is automatically
registered when they ``import yquoter``:

```bash
pip install yquoter-my-source
```

```python
from yquoter import Stock
s = Stock("cn", "000001", loader="my_source")  # auto-discovered
```

### Manual Registration (Legacy)

```python
from yquoter import register_source

@register_source("my_source", "history")
def my_history(market, code, start, end, **kwargs):
    ...
```

---

## Publishing to PyPI

Example ``pyproject.toml`` for a distributable plugin:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "yquoter-my-source"
version = "0.1.0"
description = "My custom Yquoter data source"
requires-python = ">=3.9"
dependencies = ["yquoter>=0.3.2"]

[project.entry-points."yquoter.data_sources"]
my_source = "yquoter_my_source:MyDataSource"

[tool.setuptools.packages.find]
include = ["yquoter_my_source*"]
```

Publish:

```bash
pip install build twine
python -m build
python -m twine upload dist/*
```

---

## Testing

Base your plugin tests on ``MockDataSource`` from the Yquoter test suite:

```python
import pandas as pd
from yquoter import Stock
from yquoter.datasource import _SOURCE_REGISTRY
from yquoter.plugin_base import DataSource

class TestMySource:
    def test_get_history(self):
        _SOURCE_REGISTRY["my_source"] = MyDataSource()
        s = Stock("cn", "MOCK", loader="my_source")
        df = s.get_history(start_date="20250101", end_date="20250102")
        assert not df.empty
        _SOURCE_REGISTRY.pop("my_source", None)
```

Run tests without network access:

```bash
pytest tests/ --cov=my_package
```

---

## Reference

- :class:`yquoter.plugin_base.DataSource` — full ABC API
- :mod:`yquoter.datasource` — registry and dispatch
- ``tests/conftest.py`` — ``MockDataSource`` reference implementation
- ``tests/test_plugin_base.py`` — tests for built-in sources

---

## Chart Renderer Plugins

### Chart Concept

Yquoter's report generation produces candlestick charts.  The **chart
renderer** layer abstracts *how* the chart is drawn so users can select
or swap backends without changing the rest of the report pipeline.

Two output formats are supported:

| Output format | Image model | Example use |
|---------------|-------------|-------------|
| ``"markdown"`` | Static image embedded as ``data:`` URI (PNG or SVG) | GitHub README, note apps |
| ``"html"``     | HTML fragment — ``<svg>...</svg>`` or ``<div>`` + JS | Browser viewing, dashboards |

Because standard Markdown cannot execute JavaScript, only static images
are valid for Markdown output.  HTML output unlocks interactive charts
(Plotly hover, zoom, pan).

### ChartRenderer Protocol

Every chart renderer conforms to the :class:`ChartRenderer` protocol:

```python
from typing import Protocol

class ChartRenderer(Protocol):
    """Protocol for chart rendering backends."""

    name: str  # "matplotlib" | "svg" | "plotly"

    def render(self, df, code: str, title: str, ylabel: str) -> bytes:
        """Render a static image.

        Returns:
            PNG bytes (matplotlib, plotly) or SVG bytes (svg backend).
        """
        ...

    def render_interactive(self, df, code: str, title: str, ylabel: str) -> str:
        """Render an interactive HTML fragment.

        Returns:
            HTML string (``<div id="...">`` with Plotly JS, or ``<svg>``).

        Raises:
            NotImplementedError: If the renderer does not support
                interactive output.
        """
        ...

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` if the required libraries are installed."""
        ...
```

The input DataFrame **must be preprocessed** before calling any render
method: a ``pd.DataFrame`` with a ``DatetimeIndex`` and columns
``Open``, ``High``, ``Low``, ``Close``, ``Volume``, and optionally
``MA20``.  Preprocessing is provided by the standalone utility
:func:`prepare_chart_data` (see below).

### Built-in Renderers

Yquoter ships with three renderers:

| Name | ``render()`` output | ``render_interactive()`` | Dependencies |
|------|---------------------|--------------------------|--------------|
| ``"matplotlib"`` | PNG bytes | ``NotImplementedError`` | ``matplotlib`` + ``mplfinance`` |
| ``"svg"`` | SVG bytes | ``NotImplementedError`` | **None** (stdlib only) |
| ``"plotly"`` | PNG bytes (via kaleido) | ``<div>`` + Plotly.js | ``plotly``, ``kaleido`` (PNG only) |

The **SVG renderer** is the universal fallback.  It uses only the Python
standard library (``xml.etree.ElementTree`` + ``math``) and ``pandas``,
so it is always available and guarantees chart generation even when no
optional plotting library is installed.

### Render Function

The public entry point for chart rendering is :func:`render_chart`:

```python
from yquoter.reporting import render_chart

chart_str = render_chart(
    df_ready,           # preprocessed DataFrame
    code="600519",
    backend="auto",     # "auto" | "matplotlib" | "svg" | "plotly"
    fmt="markdown",     # "markdown" | "html"
    title="600519 K-Line Chart",
    ylabel="Price (CNY)",
)
```

- ``fmt="markdown"`` → returns a ``data:image/...;base64,...`` URI string
- ``fmt="html"`` → returns an HTML fragment (``<svg>...</svg>`` or ``<div id="...">`` with JS)
- ``backend="auto"`` auto-selects the best available backend:
  - for Markdown: ``matplotlib`` > ``svg``
  - for HTML: ``plotly`` > ``svg``

The preprocessing utility is also public:

```python
from yquoter.reporting import prepare_chart_data

df_ready, error = prepare_chart_data(df_history, code="600519")
if error:
    print(f"Chart unavailable: {error}")
```

This separation keeps :func:`render_chart` pure — it only renders, and
does not mutate or validate the input.

### ReportConfig Integration

The :class:`Stock.get_report` method accepts a :class:`ReportConfig`
dataclass that bundles all report-generation options:

```python
from dataclasses import dataclass

@dataclass
class ReportConfig:
    language: str = "en"                 # "en" | "cn"
    output_format: str = "markdown"      # "markdown" | "html"
    chart_backend: str = "auto"          # "auto" | "matplotlib" | "svg" | "plotly"
    output_dir: str | None = None        # defaults to "./out"
    llm_provider: str | None = None      # e.g. "deepseek", "openai"
```

Usage:

```python
from yquoter import Stock, ReportConfig

s = Stock("cn", "600519")

# Default: Markdown + auto backend
s.get_report(start="2026-01-01", end="2026-05-10")

# HTML + interactive Plotly chart
s.get_report(
    start="2026-01-01", end="2026-05-10",
    config=ReportConfig(output_format="html", chart_backend="plotly"),
)

# Markdown with explicit SVG (no extra dependencies)
s.get_report(
    start="2026-01-01", end="2026-05-10",
    config=ReportConfig(chart_backend="svg"),
)
```

The report engine internally:

1. Fetches data concurrently (history, realtime, profile, factors)
2. Calls :func:`prepare_chart_data` on the history DataFrame
3. Calls :func:`render_chart` with the selected backend and format
4. Assembles the report sections and writes the file (``.md`` or ``.html``)

### Custom Renderer

Implement the :class:`ChartRenderer` protocol, then register:

```python
from yquoter.chart_renderer import register_renderer

class MyRenderer:
    name = "my_renderer"

    def render(self, df, code, title, ylabel):
        # Return PNG or SVG bytes
        ...

    def render_interactive(self, df, code, title, ylabel):
        # Return HTML string
        ...

    @staticmethod
    def is_available():
        return True

register_renderer(MyRenderer())

# Use it
from yquoter.reporting import render_chart
render_chart(df, "600519", backend="my_renderer", fmt="html")
```

### Chart Registration & Auto-Resolution

Renderers are stored in a module-level registry:

```python
# yquoter.chart_renderer
_RENDERER_REGISTRY: dict[str, ChartRenderer] = {}

def register_renderer(renderer: ChartRenderer) -> None:
    _RENDERER_REGISTRY[renderer.name] = renderer

def get_renderer(name: str) -> ChartRenderer:
    ...
```

When ``backend="auto"``, the resolution logic picks the first available
renderer from a priority list:

| Target format | Priority order |
|---------------|----------------|
| ``"markdown"`` | ``matplotlib`` → ``svg`` |
| ``"html"``     | ``plotly`` → ``svg`` |

The ``"svg"`` renderer is always available, so ``"auto"`` never fails.

If the user requests a specific backend that is not installed, a
``RuntimeError`` is raised with an install hint:

    Plotly is not installed. Install with: pip install yquoter[plotly]

A new ``plotly`` extra is added to ``pyproject.toml``:

```toml
[project.optional-dependencies]
plotly = ["plotly>=5.0", "kaleido>=0.2"]
```

### Summary: Data Source vs Chart Renderer

| Aspect | DataSource plugin | ChartRenderer plugin |
|--------|-------------------|----------------------|
| **What it provides** | Market data (OHLCV, quotes, financials) | Chart images (PNG, SVG, HTML) |
| **Abstract base** | :class:`~yquoter.plugin_base.DataSource` (ABC) | ``ChartRenderer`` (Protocol) |
| **Discovery** | ``entry_points`` group ``yquoter.data_sources`` | Manual ``register_renderer()`` |
| **Select via** | ``Stock(market, code, loader=...)`` | ``ReportConfig(chart_backend=...)`` |
| **Granularity** | Per source (implements multiple data types) | Per backend (one rendering technology) |
