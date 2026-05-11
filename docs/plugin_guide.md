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
