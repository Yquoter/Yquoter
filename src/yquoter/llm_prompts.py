# yquoter/llm_prompts.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""LLM prompt templates for AI-powered analysis in reports.

Provides bilingual (Chinese/English) financial analysis prompts and
helper functions to prepare data context for LLM consumption.
"""

from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Market analysis prompts
# ---------------------------------------------------------------------------

MARKET_ANALYSIS_SYSTEM_CN = """You are a professional financial data analyst. Your task is to provide professional, objective, and data-driven market analysis based on the user's stock historical data, company fundamentals, and real-time quotes.

Requirements:
1. Stay objective and neutral. Do not give specific buy/sell recommendations.
2. Output in Markdown format with clear section headers.
3. Keep data in its original format (Chinese and English mixed data is fine).
4. If data is insufficient, honestly state the limitations.
5. Include a disclaimer at the end of the analysis.

Format requirements:
- Use ## for section headers.
- Use **bold** for key data points.
- Use | tables | to display | data |.
"""

MARKET_ANALYSIS_SYSTEM_EN = """You are a professional financial data analyst. Your task is to provide professional, objective, and data-driven market analysis based on the user's stock historical data, company fundamentals, and real-time quotes.

Analysis guidelines:
1. Stay objective and neutral. Do not give specific buy/sell recommendations.
2. Output in Markdown format with clear section headers.
3. Keep data in its original format/language.
4. If data is insufficient, honestly state the limitations.
5. Include a disclaimer at the end of the analysis.

Format requirements:
- Use ## for section headers.
- Use **bold** for key data points.
- Use | tables | to display | data |.
"""

MARKET_ANALYSIS_TEMPLATE_CN = """Please analyze the stock {code} ({market_name}) based on the following data.

---

## Company Overview

| Field | Value |
| :--- | :--- |
| **Company Name** | {company_name} |
| **Industry** | {industry} |
| **Listing Date** | {list_date} |
| **Description** | {description} |

---

## Real-time Quote

| Metric | Value |
| :--- | :--- |
| **Latest Price** | {latest_price} |
| **Open** | {open_price} |
| **High** | {high_price} |
| **Low** | {low_price} |
| **Volume** | {volume} |

---

## Recent Market Data ({date_range})

```
{market_data_preview}
```

---

## Technical Indicators Summary

| Indicator | Value |
| :--- | :--- |
| **{ma_desc}** | {ma_value} |
| **{rsi_desc}** | {rsi_value} |
| {additional_indicators}

---

Please analyze the following aspects:

### 1. Performance Summary
How did the stock perform during {date_range}? Focus on trend direction and volatility characteristics.

### 2. Event-Driven Analysis
What major economic events, industry policies, or company announcements may have driven the price movements during this period?

### 3. Technical Analysis
Provide technical insights based on moving averages, RSI, volume patterns, and other indicators.

### 4. Risks and Opportunities
What are the key risk factors and potential opportunities at this stage?

### 5. Key References
Based on the above analysis, what key information should investors pay attention to at this stage?

---

*Disclaimer: This analysis is AI-generated for reference and educational purposes only. It does not constitute investment advice. Always do your own research.*
"""

MARKET_ANALYSIS_TEMPLATE_EN = """Please analyze the stock **{code}** ({market_name}) based on the following data.

---

## Company Overview

| Metric | Value |
| :--- | :--- |
| **Company Name** | {company_name} |
| **Industry** | {industry} |
| **Listing Date** | {list_date} |
| **Description** | {description} |

---

## Real-time Quote

| Metric | Value |
| :--- | :--- |
| **Latest Price** | {latest_price} |
| **Open** | {open_price} |
| **High** | {high_price} |
| **Low** | {low_price} |
| **Volume** | {volume} |

---

## Recent Market Data ({date_range})

```
{market_data_preview}
```

---

## Technical Indicators Summary

| Indicator | Value |
| :--- | :--- |
| **{ma_desc}** | {ma_value} |
| **{rsi_desc}** | {rsi_value} |
| {additional_indicators}

---

Please analyze the following aspects:

### 1. Performance Summary
How did the stock perform during the {date_range} period? Focus on trend direction and volatility characteristics.

### 2. Event-Driven Analysis
What major economic events, industry policies, or company announcements may have driven the price movements during this period?

### 3. Technical Analysis
Provide technical insights based on moving averages, RSI, volume patterns, and other indicators.

### 4. Risks and Opportunities
What are the key risk factors and potential opportunities at this stage?

### 5. Key References
Based on the above analysis, what key information should investors pay attention to at this stage?

---

*Disclaimer: This analysis is AI-generated for reference and educational purposes only. It does not constitute investment advice. Always do your own research.*
"""

# ---------------------------------------------------------------------------
# Data preparation helpers
# ---------------------------------------------------------------------------


def _market_name(market: str) -> str:
    """Convert a market identifier to a human-readable name.

    Args:
        market: Market identifier (``'cn'``, ``'hk'``, ``'us'``).

    Returns:
        str: Human-readable market name.
    """
    names = {
        "cn": "China A-Share / A股",
        "hk": "Hong Kong / 港股",
        "us": "US Stock / 美股",
    }
    return names.get(market, market.upper())


def prepare_analysis_context(
    market: str,
    code: str,
    df_history: "pd.DataFrame",  # type: ignore
    df_realtime: "pd.DataFrame",  # type: ignore
    profile: "pd.DataFrame",  # type: ignore
    language: str = "cn",
    additional_indicators: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Prepare data context for LLM analysis.

    Converts DataFrame data into LLM-friendly text summary format.

    Args:
        market: Market identifier.
        code: Stock code.
        df_history: Historical OHLCV DataFrame.
        df_realtime: Real-time quote DataFrame.
        profile: Company profile DataFrame.
        language: Report language (``'cn'`` or ``'en'``).
        additional_indicators: Extra indicator key-value pairs.

    Returns:
        Dict[str, str]: Formatted context data for template filling.
    """
    import pandas as pd

    # --- Extract company info from profile ---
    company_name = "N/A"
    industry = "N/A"
    list_date = "N/A"
    description = "N/A"

    if not profile.empty:
        p = profile.iloc[0]
        company_name = str(
            p.get("name", p.get("NAME", p.get("ORG_NAME", "N/A")))
        )
        industry = str(
            p.get("industry", p.get("INDUSTRY", p.get("BELONG_INDUSTRY", "N/A")))
        )
        list_date = str(
            p.get("list_date", p.get("LISTING_DATE", "N/A"))
        )[:10]
        description = str(
            p.get("description", p.get("MAIN_BUSINESS", p.get("ORG_PROFILE", "N/A")))
        )[:300]

    # --- Extract real-time data ---
    latest_price = "N/A"
    open_price = "N/A"
    high_price = "N/A"
    low_price = "N/A"
    volume = "N/A"

    if not df_realtime.empty:
        r = df_realtime.iloc[0]
        latest_price = str(r.get("close", r.get("latest", "N/A")))
        open_price = str(r.get("open", "N/A"))
        high_price = str(r.get("high", "N/A"))
        low_price = str(r.get("low", "N/A"))
        volume = str(r.get("vol", r.get("volume", "N/A")))

    # --- Prepare historical data preview ---
    date_range = "N/A"
    market_data_preview = "No data available."

    if not df_history.empty and isinstance(df_history, pd.DataFrame):
        date_col = (
            "date" if "date" in df_history.columns else df_history.index.name
        )
        if date_col and date_col in df_history.columns:
            try:
                start_s = str(df_history[date_col].iloc[0])[:10]
                end_s = str(df_history[date_col].iloc[-1])[:10]
                date_range = f"{start_s} ~ {end_s}"
            except Exception:
                date_range = "N/A"

        preview_cols = []
        for col in ["date", "open", "high", "low", "close", "vol", "change%"]:
            if col in df_history.columns:
                preview_cols.append(col)

        if preview_cols:
            try:
                preview_df = df_history[preview_cols].tail(10)
                market_data_preview = preview_df.to_string(index=False)
            except Exception:
                market_data_preview = "Data preview unavailable."

    # --- Build indicator summary ---
    ma_desc = "MA5" if language == "en" else "MA5"
    ma_value = "N/A"
    rsi_desc = "RSI14" if language == "en" else "RSI14"
    rsi_value = "N/A"
    additional_text = ""

    if additional_indicators:
        if "ma" in additional_indicators:
            ma_value = additional_indicators["ma"]
        if "rsi" in additional_indicators:
            rsi_value = additional_indicators["rsi"]

        extra_lines = []
        for key, value in additional_indicators.items():
            if key not in ("ma", "rsi"):
                label = key.upper() if language == "en" else key
                extra_lines.append(f"| **{label}** | {value} |")
        if extra_lines:
            additional_text = "\n".join(extra_lines)

    if date_range == "N/A":
        date_range_text = "recent period"
    else:
        date_range_text = date_range

    return {
        "code": code,
        "market_name": _market_name(market),
        "company_name": company_name,
        "industry": industry,
        "list_date": list_date,
        "description": description,
        "latest_price": latest_price,
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "volume": volume,
        "date_range": date_range_text,
        "market_data_preview": market_data_preview,
        "ma_desc": ma_desc,
        "ma_value": ma_value,
        "rsi_desc": rsi_desc,
        "rsi_value": rsi_value,
        "additional_indicators": additional_text,
    }


def get_analysis_prompt(
    language: str = "cn",
) -> tuple:
    """Get the analysis prompt pair (system + user template).

    Args:
        language: Template language (``'cn'`` or ``'en'``).

    Returns:
        tuple: ``(system_prompt, user_template)``.
    """
    if language == "cn":
        return MARKET_ANALYSIS_SYSTEM_CN, MARKET_ANALYSIS_TEMPLATE_CN
    return MARKET_ANALYSIS_SYSTEM_EN, MARKET_ANALYSIS_TEMPLATE_EN
