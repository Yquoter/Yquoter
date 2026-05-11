#!/usr/bin/env python3
"""Plugin system example: create and use a custom DataSource.

This script demonstrates the three ways to plug a data source into Yquoter:

1. **Direct instance** — pass a DataSource object to Stock
2. **Manual registration** — add to _SOURCE_REGISTRY and use by name
3. **Decorator-style** — register individual functions (legacy compat)
4. **Entry-point discovery** — auto-discover from installed packages (recommended)

Run:
    python examples/plugin_example.py
"""

from typing import Optional, Union, List
import pandas as pd

from yquoter import Stock, DataSource, register_source, set_default_source
from yquoter.datasource import _SOURCE_REGISTRY


# ---------------------------------------------------------------------------
# Step 1: Define a minimal custom DataSource
# ---------------------------------------------------------------------------

class MySimpleSource(DataSource):
    """A trivial data source that returns synthetic data."""

    name = "my_simple"
    supported_types = {"history", "realtime", "profile"}

    def get_history(self, market, code, start, end, klt=101, fqt=1,
                    fields="basic", **kwargs) -> pd.DataFrame:
        return pd.DataFrame({
            "date":   ["20260501", "20260502", "20260503"],
            "open":   [100.0, 101.0, 99.5],
            "high":   [102.0, 103.0, 101.0],
            "low":    [99.0,  100.0, 98.5],
            "close":  [101.0, 99.5,  100.5],
            "vol":    [10000, 12000, 9500],
            "amount": [1010000, 1194000, 954750],
        })

    def get_realtime(self, market, code,
                     fields: Optional[Union[str, List[str]]] = None,
                     **kwargs) -> pd.DataFrame:
        codes = code if isinstance(code, list) else [code]
        return pd.DataFrame({
            "code": codes,
            "name": ["MyStock"] * len(codes),
            "open":  [100.0] * len(codes),
            "high":  [102.0] * len(codes),
            "low":   [99.0] * len(codes),
            "close": [101.0] * len(codes),
            "vol":   [10000] * len(codes),
            "amount":[1010000] * len(codes),
        })

    def get_profile(self, market, code, **kwargs) -> pd.DataFrame:
        return pd.DataFrame({
            "CODE": [code],
            "NAME": ["My Custom Stock"],
            "INDUSTRY": ["Technology"],
            "MAIN_BUSINESS": ["Demonstrating Yquoter plugin system."],
            "LISTING_DATE": ["2025-01-01"],
        })


# ---------------------------------------------------------------------------
# Usage 1: Direct instance (no registration needed)
# ---------------------------------------------------------------------------

print("=" * 60)
print("1. Direct DataSource instance")
print("=" * 60)

# Use an uncached code so our mock source is actually called
s = Stock("cn", "999999", loader=MySimpleSource())
print(f"Stock: {s!r}")
print(f"Profile:\n{s.get_profile().to_string()}\n")
print(f"History:\n{s.get_history(start_date='2026-05-01').to_string()}\n")
print(f"Realtime:\n{s.get_realtime().to_string()}\n")


# ---------------------------------------------------------------------------
# Usage 2: Manual registration (use by name)
# ---------------------------------------------------------------------------

print("=" * 60)
print("2. Register a DataSource and use by name")
print("=" * 60)

register_source("my_source", MySimpleSource())
s2 = Stock("cn", "000001", loader="my_source")
print(f"Available sources: {list(_SOURCE_REGISTRY.keys())}")
print(f"Realtime via 'my_source':\n{s2.get_realtime().to_string()}\n")

# Set as default (pass loader=None to use the default source)
set_default_source("my_source")
s3 = Stock("cn", "600036", loader=None)
print(f"Default source now: {s3.loader}")
print(f"History via default:\n{s3.get_history(start_date='2026-05-01').to_string()}\n")

# Restore default
set_default_source("spider")


# ---------------------------------------------------------------------------
# Usage 3: Decorator-style function registration (legacy compat)
# ---------------------------------------------------------------------------

print("=" * 60)
print("3. Decorator-style registration (legacy compat)")
print("=" * 60)


@register_source("custom_realtime", "realtime")
def my_realtime_func(market, code, fields=None, **kwargs):
    return pd.DataFrame({
        "code": [code],
        "name": ["DecoratedSource"],
        "close": [99.99],
        "vol":   [5000],
        "amount":[500000],
    })


s4 = Stock("cn", "600519", loader="custom_realtime")
print(f"Realtime via decorator:\n{s4.get_realtime().to_string()}\n")


# ---------------------------------------------------------------------------
# Usage 4: Entry-point discovery (recommended for published plugins)
# ---------------------------------------------------------------------------

print("=" * 60)
print("4. Entry-point discovery (recommended for packages)")
print("=" * 60)
print("Add to your package's pyproject.toml:")
print()
print("    [project.entry-points.\"yquoter.data_sources\"]")
print("    my_source = \"my_package:MySimpleSource\"")
print()
print("After pip install, Yquoter auto-discovers the source on import.")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

for name in ("my_source", "custom_realtime"):
    _SOURCE_REGISTRY.pop(name, None)

print()
print("=" * 60)
print("Plugin example complete.")
print("=" * 60)
