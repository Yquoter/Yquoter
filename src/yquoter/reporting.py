# yquoter/reporting.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import base64
import os
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd
from datetime import datetime, timedelta

from tabulate import tabulate as _tabulate

from yquoter.logger import get_logger
from yquoter.config import LOCALIZATION
from yquoter.exceptions import ParameterError
from yquoter.indicators import _get_ma_n
from yquoter.spider_core import _run_async
from yquoter.chart_renderer import (
    get_renderer,
    _resolve_backend,
)
from yquoter.datasource import (
    _get_stock_history,
    _get_stock_realtime,
    _get_stock_profile,
    _get_stock_factors,
    _aget_stock_history,
    _aget_stock_realtime,
    _aget_stock_profile,
    _aget_stock_factors,
)


logger = get_logger(__name__)


def prepare_chart_data(df_history: pd.DataFrame, code: str):
    """Validate and prepare OHLCV data for chart rendering.

    Args:
        df_history: Raw historical OHLCV DataFrame.
        code: Stock code for error messages.

    Returns:
        Tuple of ``(df_plot, error_reason)``. On success, *df_plot* is
        a prepared DataFrame with DatetimeIndex and renamed columns;
        *error_reason* is ``None``. On failure, *df_plot* is ``None``
        and *error_reason* describes the problem.
    """
    if df_history.empty:
        return None, f"Empty DataFrame for stock {code}"

    df_plot = df_history.copy()

    try:
        df_plot = _get_ma_n(n=20, df=df_plot)
    except Exception as e:
        logger.warning("Failed to calculate MA20 for stock %s: %s", code, str(e))

    try:
        if 'date' in df_plot.columns:
            df_plot['date'] = pd.to_datetime(df_plot['date'], errors='coerce')
            df_plot.set_index('date', inplace=True)
        elif not isinstance(df_plot.index, pd.DatetimeIndex):
            return None, f"Invalid datetime index for stock {code}"

        column_map = {
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'vol': 'Volume',
        }
        df_plot.rename(columns=column_map, inplace=True)

        required_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df_plot.columns for col in required_cols):
            return None, f"Missing OHLC columns for stock {code}"
    except Exception as e:
        return None, f"Data preparation failed for stock {code}: {e}"

    return df_plot, None


def render_chart(
    df: pd.DataFrame,
    code: str,
    *,
    backend: str = "auto",
    fmt: str = "markdown",
    title: str = "",
    ylabel: str = "Price",
) -> Optional[str]:
    """Render a candlestick chart as a format-appropriate string.

    Args:
        df: Preprocessed DataFrame with DatetimeIndex and columns
            ``Open``, ``High``, ``Low``, ``Close``, ``Volume``,
            and optionally ``MA20``.
        code: Stock ticker symbol for labelling.
        backend: Chart backend name. ``"auto"`` picks the best available.
        fmt: Output format. ``"markdown"`` returns a ``data:`` URI;
            ``"html"`` returns an HTML fragment.
        title: Chart title text.
        ylabel: Y-axis label text.

    Returns:
        - For ``fmt="markdown"``: ``data:image/...;base64,...`` URI string.
        - For ``fmt="html"``: HTML fragment (``<svg>`` or ``<div>`` + JS).
        - ``None`` if rendering fails.
    """
    try:
        name = _resolve_backend(backend, fmt)
    except RuntimeError as e:
        logger.error("Chart backend resolution failed: %s", e)
        return None

    try:
        renderer = get_renderer(name)
    except KeyError:
        logger.error("Chart renderer '%s' is not registered.", name)
        return None

    try:
        if fmt == "markdown":
            img_bytes = renderer.render(df, code, title, ylabel)
            if name == "svg" or getattr(renderer, "name", "") == "svg":
                mime = "image/svg+xml"
            else:
                mime = "image/png"
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        else:  # html
            try:
                return renderer.render_interactive(df, code, title, ylabel)
            except NotImplementedError:
                svg_bytes = renderer.render(df, code, title, ylabel)
                return svg_bytes.decode("utf-8")
    except Exception as e:
        logger.error("Chart rendering failed (backend=%s, fmt=%s): %s", name, fmt, e)
        return None





# ======================================================================
# ReportConfig
# ======================================================================


@dataclass
class ReportConfig:
    """Configuration for stock report generation.

    All fields have sensible defaults so ``ReportConfig()`` produces
    a standard Markdown report with auto-detected chart backend.

    Attributes:
        language: Report language (``"en"`` or ``"cn"``).
        output_format: ``"markdown"`` for Markdown with data: URIs,
            ``"html"`` for interactive browser rendering.
        chart_backend: ``"auto"`` (best available), ``"matplotlib"``,
            ``"svg"``, or ``"plotly"``.
        output_dir: Directory for the saved report file.
            ``None`` defaults to ``./out``.
        llm_provider: Optional LLM provider name for AI analysis
            (e.g. ``"deepseek"``, ``"openai"``).
    """
    language: str = "en"
    output_format: str = "markdown"
    chart_backend: str = "auto"
    output_dir: Optional[str] = None
    llm_provider: Optional[str] = None


# ======================================================================
# Sync front-end
# ======================================================================


def _generate_stock_report(
        market: str,
        code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: Optional[str] = None,
        language: str = 'en',
        output_dir: Optional[str] = None,
        llm_provider: Optional[str] = None,
        config: Optional[ReportConfig] = None,
) -> str:
    """Generate a comprehensive stock analysis report.

    **Sync front-end** — the async kernel fetches history, realtime,
    profile, and factors **concurrently** to minimise wall-clock time.

    Args:
        market: Stock exchange market identifier (e.g., ``'cn'``).
        code: Stock symbol/ticker.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        source: Data source provider name.
        language: Report language.  **Ignored if *config* is given.**
        output_dir: Directory to save the report.  **Ignored if
            *config* is given.**
        llm_provider: Optional LLM provider for AI analysis.
            **Ignored if *config* is given.**
        config: :class:`ReportConfig` instance.  When provided,
            *language*, *output_dir*, and *llm_provider* are taken
            from *config* instead of the individual parameters.

    Returns:
        str: The full report in Markdown or HTML format.
    """
    if config is not None:
        language = config.language
        output_dir = config.output_dir
        llm_provider = config.llm_provider
        effective_config = config
    else:
        effective_config = ReportConfig(
            language=language,
            output_format="markdown",
            chart_backend="auto",
            output_dir=output_dir,
            llm_provider=llm_provider,
        )

    return _run_async(
        _async_generate_stock_report(
            market=market, code=code,
            start=start, end=end,
            source=source,
            config=effective_config,
        )
    )


# ======================================================================
# Async kernel
# ======================================================================


async def _async_generate_stock_report(
        market: str,
        code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: Optional[str] = None,
        config: ReportConfig = ReportConfig(),
) -> str:
    """Async kernel: data fetching runs concurrently via thread pool.

    This function is wrapped by :func:`_generate_stock_report` which
    bridges it back to synchronous callers.

    Args:
        market: Stock exchange market identifier (e.g., ``'cn'``).
        code: Stock symbol/ticker.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        source: Data source provider name.
        config: :class:`ReportConfig` instance with all rendering
            and output options.

    Returns:
        str: The full report in Markdown or HTML format.
    """
    # ---- validate & prepare ----
    if not market or not code:
        raise ParameterError("Both market and code parameters are required")

    # ---- unpack config ----
    language = config.language
    output_dir = config.output_dir
    llm_provider = config.llm_provider
    output_format = config.output_format
    chart_backend = config.chart_backend

    # ---- date defaults ----
    today = datetime.now()
    if start is None and end is None:
        start = (today - timedelta(days=30)).strftime('%Y%m%d')
        end = today.strftime('%Y%m%d')
    elif start is None:
        try:
            end_date = datetime.strptime(end, '%Y%m%d')
        except ValueError:
            end_date = today
        start = (end_date - timedelta(days=30)).strftime('%Y%m%d')
    elif end is None:
        end = today.strftime('%Y%m%d')

    lang_key = 'cn' if language.lower() == 'cn' else 'en'
    try:
        L = LOCALIZATION[lang_key]
    except KeyError:
        logger.warning("Language '%s' not found, defaulting to English", language)
        L = LOCALIZATION['en']

    # ---- concurrent data collection (all in same event loop) ----
    trade_date = end.replace("-", "")[:8]

    # Stagger start times to avoid Eastmoney rate-limiting
    async def _delayed(coro, delay: float):
        await asyncio.sleep(delay)
        return await coro

    results = await asyncio.gather(
        _aget_stock_history(market=market, code=code, start=start, end=end, source=source),
        _delayed(_aget_stock_realtime(market=market, code=code, source=source), 0.3),
        _delayed(_aget_stock_profile(market=market, code=code, source=source), 0.6),
        _delayed(_aget_stock_factors(market=market, code=code, trade_date=trade_date, source=source), 0.9),
        return_exceptions=True,
    )

    # Unpack results (partial failures are tolerated)
    df_history: Optional[pd.DataFrame] = None
    df_realtime: Optional[pd.DataFrame] = None
    profile: Optional[pd.DataFrame] = None
    df_factors: Optional[pd.DataFrame] = None
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Data source %d failed (continuing): %s", i, r)
            continue
        if i == 0:
            df_history = r
        elif i == 1:
            df_realtime = r
        elif i == 2:
            profile = r
        elif i == 3:
            df_factors = r

    # ---- report assembly (all sync) ----
    report_sections: list[str] = []

    # 1. Header
    report_sections.extend([
        f"# {code} ({market.upper()}) {L['title_report']}",
        f"### {L['header_generated']}: {today.strftime('%Y-%m-%d %H:%M:%S')}",
        f"### {L['header_history']}: {start} - {end}\n",
    ])

    # 2. Profile
    report_sections.append(f"## {L['title_profile']}")
    if profile is not None and not profile.empty:
        p = profile.iloc[0]
        description = p.get('description', p.get('MAIN_BUSINESS', L['no_description']))
        report_sections.extend([
            f"**{L['label_name']}:** {p.get('name', p.get('NAME', 'N/A'))}",
            f"**{L['label_industry']}:** {p.get('industry', p.get('INDUSTRY', 'N/A'))}",
            f"**{L['label_list_date']}:** {p.get('list_date', p.get('LISTING_DATE', 'N/A'))}",
            f"**{L['label_desc']}:** \n> {description}\n",
        ])
    else:
        report_sections.append(L['missing_profile'] + "\n")

    # 3. Realtime
    report_sections.append(f"## {L['title_realtime']}")
    if df_realtime is not None and not df_realtime.empty:
        data = df_realtime.iloc[0]

        def _fmt_price(val) -> str:
            if isinstance(val, (int, float, str)) and str(val).replace('.', '', 1).isdigit():
                return f"${float(val):.2f}"
            return str(val) if val is not None else 'N/A'

        def _fmt_vol(val) -> str:
            if isinstance(val, (int, float, str)) and str(val).replace('.', '', 1).isdigit():
                return f"{float(val):,.0f}"
            return str(val) if val is not None else 'N/A'

        report_sections.extend([
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| {L['label_latest_price']} | {_fmt_price(data.get('close', 'N/A'))} |",
            f"| {L['label_open']} | {_fmt_price(data.get('open', 'N/A'))} |",
            f"| {L['label_high']} | {_fmt_price(data.get('high', 'N/A'))} |",
            f"| {L['label_low']} | {_fmt_price(data.get('low', 'N/A'))} |",
            f"| {L['label_volume']} | {_fmt_vol(data.get('vol', 'N/A'))} |\n",
        ])
    else:
        report_sections.append(L['missing_realtime'] + "\n")

    # 4. Chart
    plot_title = f'{code} {L["title_chart"]}'
    plot_ylabel = f'{L["price_unit"]} '
    if df_history is not None and not df_history.empty:
        try:
            df_plot, err = prepare_chart_data(df_history, code)
            if df_plot is not None:
                chart_str = render_chart(
                    df_plot, code,
                    backend=chart_backend,
                    fmt=output_format,
                    title=plot_title,
                    ylabel=plot_ylabel,
                )
                if chart_str:
                    if output_format == "html":
                        report_sections.extend([
                            f"<h2>{L['title_chart']}</h2>",
                            chart_str,
                        ])
                    else:
                        report_sections.extend([
                            f"## {L['title_chart']}",
                            f"![{code} K-Line Chart]({chart_str})\n",
                        ])
                else:
                    report_sections.append(f"## {L['chart_unavailable']}\n{L['chart_note']}\n")
            else:
                report_sections.append(f"## {L['chart_unavailable']}\n{L['chart_note']}\n")
        except Exception as e:
            logger.error("Chart generation failed: %s", e)
            report_sections.append(f"## {L['chart_unavailable']}\n{L['chart_note']}\n")
    else:
        report_sections.append(f"## {L['chart_unavailable']}\n{L['chart_note']}\n")

    # 5. Summary statistics
    report_sections.append(f"## {L['title_summary']}")
    if df_history is not None and not df_history.empty:
        try:
            summary = (
                df_history.select_dtypes(include=['number'])
                .describe()
                .transpose()
            )
            report_sections.append(summary.to_markdown())
        except Exception as e:
            logger.error("Summary failed: %s", e)
            report_sections.append(L['missing_history'])
    else:
        report_sections.append(L['missing_history'])

    # ==============================================================
    # 6. AI-Assisted Smart Analysis Section
    # ==============================================================
    if llm_provider:
        try:
            from yquoter.llm_gateway import LLMGateway, LLMNotAvailableError
            from yquoter.llm_prompts import (
                prepare_analysis_context,
                get_analysis_prompt,
            )

            gateway = LLMGateway()
            if gateway.is_available():
                logger.info("Preparing AI analysis via %s...", llm_provider)

                indicators: Dict[str, str] = {}

                # --- indicators (pandas on already-fetched df_history) ---
                if df_history is not None and not df_history.empty:
                    dh = df_history['close'].astype(float)
                    if len(dh) >= 5:
                        try:
                            ma5 = dh.rolling(5).mean().iloc[-1]
                            indicators["ma"] = f"{ma5:.2f}"
                        except Exception:
                            pass
                    if len(dh) >= 14:
                        try:
                            delta = dh.diff()
                            gain = delta.where(delta > 0, 0).rolling(14).mean()
                            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                            rs = gain / loss.replace(0, float('nan'))
                            rsi = 100 - (100 / (1 + rs))
                            indicators["rsi"] = f"{rsi.iloc[-1]:.1f}"
                        except Exception:
                            pass
                    if len(dh) >= 20:
                        try:
                            avg_vol = df_history['vol'].astype(float).rolling(20).mean()
                            ratio = df_history['vol'].astype(float) / avg_vol
                            indicators["volume_ratio"] = f"{ratio.iloc[-1]:.2f}"
                        except Exception:
                            pass

                # --- factors (already fetched in the gather) ---
                if df_factors is not None and not df_factors.empty:
                    f_row = df_factors.iloc[0]
                    if "PE_TTM" in df_factors.columns:
                        indicators["PE_TTM"] = str(f_row.get("PE_TTM", "N/A"))
                    if "PB_MRQ" in df_factors.columns:
                        indicators["PB_MRQ"] = str(f_row.get("PB_MRQ", "N/A"))

                safe_profile = (
                    profile if profile is not None and not profile.empty
                    else pd.DataFrame()
                )
                context = prepare_analysis_context(
                    market=market, code=code,
                    df_history=df_history if df_history is not None else pd.DataFrame(),
                    df_realtime=df_realtime if df_realtime is not None else pd.DataFrame(),
                    profile=safe_profile,
                    language=language,
                    additional_indicators=indicators or None,
                )
                sys_prompt, user_tmpl = get_analysis_prompt(
                    language=language
                )
                user_prompt = user_tmpl.format(**context)

                analysis = gateway.analyze(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    provider_name=llm_provider,
                    temperature=0.3,
                    max_tokens=2048,
                )

                if analysis:
                    ai_title = (
                        "AI Smart Analysis"
                    )
                    ai_disclaimer = (
                        "\n---\n*This analysis is AI-generated for "
                        "reference and educational purposes only.*"
                    )
                    report_sections.append(f"\n## {ai_title}\n")
                    report_sections.append(analysis)
                    report_sections.append(ai_disclaimer)
                    logger.info("AI analysis section added to report.")
                else:
                    logger.warning("LLM returned empty analysis.")
            else:
                logger.warning(
                    "No LLM provider configured. "
                    "Cannot fulfill llm_provider='%s'.", llm_provider
                )

        except (ImportError, LLMNotAvailableError) as e:
            logger.warning(
                "AI analysis unavailable (llm_provider='%s'): %s",
                llm_provider, e,
            )
        except Exception as e:
            logger.warning("AI analysis failed (non-critical): %s", e)

    # ---- compile & save ----
    if output_format == "html":
        final_report = _wrap_html_report(report_sections, code, market.upper())
        ext = ".html"
    else:
        final_report = "\n".join(report_sections)
        ext = ".md"

    target_dir = output_dir or os.path.join(os.getcwd(), 'out')
    try:
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{code}_report_{today.strftime('%Y%m%d_%H%M%S')}{ext}"
        file_path = os.path.join(target_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
        logger.info("Report saved to: %s", file_path)
    except Exception as e:
        logger.error("Failed to save report: %s", e)

    return final_report


def _wrap_html_report(sections: list[str], code: str, market: str) -> str:
    """Wrap report sections in a minimal HTML document."""
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{code} ({market}) Stock Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 960px; margin: 0 auto; padding: 20px; background: #1a1a2e;
         color: #e0e0e0; }}
  h1, h2, h3 {{ color: #ffffff; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ border: 1px solid #444; padding: 8px; text-align: left; }}
  th {{ background: #2a2a4a; }}
  a {{ color: #42a5f5; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


async def _async_safe_factors(market, code, trade_date) -> Optional[pd.DataFrame]:
    """Fetch factors, tolerating failures gracefully.

    Args:
        market: Stock exchange market identifier.
        code: Stock symbol/ticker.
        trade_date: Trading date in ``YYYYMMDD`` format.

    Returns:
        pd.DataFrame or None: Factor data on success, ``None`` if
        the fetch fails.
    """
    try:
        return await _aget_stock_factors(market=market, code=code, trade_date=trade_date)
    except Exception as e:
        logger.debug("Factor fetch failed (non-critical): %s", e)
        return None
