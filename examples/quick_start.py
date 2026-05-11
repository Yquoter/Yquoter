#!/usr/bin/env python3
"""Quick-start script for the Yquoter Stock API.

Demonstrates the most common workflows in a single runnable script.
Requires network access (uses the default spider data source).

Run:
    python examples/quick_start.py
"""

import pandas as pd
from yquoter import Stock, get_llm_gateway

pd.set_option("display.max_columns", 10)
pd.set_option("display.width", 120)

# ---------------------------------------------------------------------------
# 1. Create a Stock object
# ---------------------------------------------------------------------------

moutai = Stock("cn", "600519")
print(f"Stock: {moutai!r}")
print()

# ---------------------------------------------------------------------------
# 2. Company profile
# ---------------------------------------------------------------------------

profile = moutai.get_profile()
print("Profile:")
print(profile[["NAME", "INDUSTRY", "LISTING_DATE"]].to_string(index=False))
print()

# ---------------------------------------------------------------------------
# 3. Real-time quote
# ---------------------------------------------------------------------------

realtime = moutai.get_realtime()
print("Real-time:")
print(realtime[["name", "open", "high", "low", "vol"]].to_string(index=False))
print()

# ---------------------------------------------------------------------------
# 4. Historical OHLCV
# ---------------------------------------------------------------------------

history = moutai.get_history(start_date="2026-04-01", end_date="2026-05-10")
print(f"History: {len(history)} records")
print(history[["date", "open", "high", "low", "close", "vol"]].tail(3).to_string(index=False))
print()

# ---------------------------------------------------------------------------
# 5. Technical indicators
# ---------------------------------------------------------------------------

ma20 = moutai.get_ma(n=20)
print(f"MA20 (last): {ma20['MA20'].iloc[-1]:.2f}")

rsi14 = moutai.get_rsi(n=14)
print(f"RSI14 (last): {rsi14['RSI14'].iloc[-1]:.1f}")

boll = moutai.get_boll(n=20)
print(f"Bollinger (last): upper={boll['upper'].iloc[-1]:.2f}, "
      f"mid={boll['mid'].iloc[-1]:.2f}, lower={boll['lower'].iloc[-1]:.2f}")

dd = moutai.get_max_drawdown(start_date="2026-01-01")
print(f"Max drawdown: {float(dd['max_drawdown']):.2%}")
print()

# ---------------------------------------------------------------------------
# 6. Financials
# ---------------------------------------------------------------------------

fin = moutai.get_financials(end_day="2025-12-31", report_type="LRB", limit=4)
print("Financials (income statement):")
print(fin[["REPORTDATE", "BASIC_EPS", "TOTAL_OPERATE_INCOME"]].to_string(index=False))
print()

# ---------------------------------------------------------------------------
# 7. Multi-market
# ---------------------------------------------------------------------------

tencent = Stock("hk", "00700")
print(f"HK 00700: {tencent.get_profile().iloc[0]['NAME']}")

aapl = Stock("us", "AAPL")
aapl_rt = aapl.get_realtime()
print(f"US AAPL: open={aapl_rt.iloc[0].get('open', 'N/A')}")
print()

# ---------------------------------------------------------------------------
# 8. LLM Gateway status
# ---------------------------------------------------------------------------

gateway = get_llm_gateway()
print(f"LLM available: {gateway.is_available()}")
if gateway.is_available():
    print(f"Providers: {gateway.list_providers()}")
else:
    print("Set DEEPSEEK_API_KEY or similar env var to enable AI analysis.")
print()

# ---------------------------------------------------------------------------
# 9. Generate a report (without AI — no API key needed)
# ---------------------------------------------------------------------------

report = moutai.get_report(start="2026-04-01", end="2026-05-10", language="en")
print(f"Report: {len(report)} characters")
print()
print("Done. See the README and docs/plugin_guide.md for more.")
