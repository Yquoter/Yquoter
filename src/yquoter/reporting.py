# yquoter/reporting.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from yquoter.logger import get_logger
from yquoter.config import LOCALIZATION
from yquoter.exceptions import PlotLibImportError, ParameterError
from yquoter.indicators import _get_ma_n
from yquoter.spider_core import _run_async
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


def _get_plot_as_base64(df_history: pd.DataFrame, code: str, title: str,
                          ylabel: str) -> Optional[str]:
    """Generate a base64-encoded K-line (candlestick) chart.

    Uses mplfinance to plot the chart and encodes it as a base64 PNG
    string for embedding in Markdown reports.

    Args:
        df_history: DataFrame containing OHLCV stock history data.
        code: Stock code/ticker for the chart title.
        title: Title text for the chart.
        ylabel: Y-axis label text.

    Returns:
        Optional[str]: Base64-encoded PNG image string, or ``None`` if
            generation fails.
    """
    # 1. Import check with proper error handling
    try:
        import matplotlib.pyplot as plt
        import mplfinance as mpf
        import base64
        from io import BytesIO
    except PlotLibImportError as e:
        logger.warning("Visualization libraries not available: %s", e)
        return None

    # Set a font that supports Chinese
    plt.rcParams['font.sans-serif'] = [
        'Microsoft YaHei',  # Windows
        'SimHei',  # Windows
        'Arial Unicode MS',  # macOS/Linux
        'Noto Sans CJK SC',  # Google's Noto Font
        'WenQuanYi Zen Hei',  # Linux
        'sans-serif'
    ]

    # Fix negative sign display
    plt.rcParams['axes.unicode_minus'] = False

    # 2. Input validation
    if df_history.empty:
        logger.warning("Empty DataFrame received for stock %s", code)
        return None

    # 3. Data preparation
    df_plot = df_history.copy()

    # 4. Technical Indicators (with error handling)
    try:
        N = 20
        df_plot = _get_ma_n(n=N, df=df_plot)
    except Exception as e:
        logger.warning("Failed to calculate moving average for stock %s: %s", code, str(e))

    try:
        # Handle date column/index
        if 'date' in df_plot.columns:
            df_plot['date'] = pd.to_datetime(df_plot['date'], errors='coerce')
            df_plot.set_index('date', inplace=True)
        elif not isinstance(df_plot.index, pd.DatetimeIndex):
            logger.warning("Invalid datetime index for stock %s", code)
            return None

        # Column standardization
        column_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'vol': 'Volume'
        }
        df_plot.rename(columns=column_map, inplace=True)

        # Verify required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df_plot.columns for col in required_cols):
            logger.warning("Missing required OHLC columns for stock %s", code)
            return None

    except Exception as e:
        logger.error("Data preparation failed for stock %s: %s", code, str(e))
        return None

    # 5. Plot generation
    try:
        style = mpf.make_mpf_style(
            base_mpf_style='yahoo',
            gridstyle='-',
            rc={'font.family': ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']}
        )

        add_plots = []
        if 'MA20' in df_plot.columns:
            add_plots.append(
                mpf.make_addplot(df_plot['MA20'], color='b', secondary_y=False)
            )

        fig, axes = mpf.plot(
            df_plot,
            type='candle',
            style=style,
            title=title,
            ylabel=ylabel,
            volume=True,
            addplot=add_plots,
            figratio=(16, 9),
            figscale=0.8,
            returnfig=True
        )

        # 6. Save to buffer and encode
        buf = BytesIO()
        fig.savefig(
            buf,
            format='png',
            bbox_inches='tight',
            dpi=100
        )
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode('utf-8')

    except Exception as e:
        logger.error("Chart generation failed for stock %s: %s", code, str(e))
        return None


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
) -> str:
    """Generate a comprehensive stock analysis report in Markdown.

    **Sync front-end** — the async kernel fetches history, realtime,
    profile, and factors **concurrently** to minimise wall-clock time.

    The report includes company profile, real-time quote, historical
    price chart, summary statistics, and an optional AI-powered
    analysis section.

    Args:
        market: Stock exchange market identifier (e.g., ``'cn'``).
        code: Stock symbol/ticker.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        source: Data source provider name.
        language: Report language. ``"en"`` for English,
            ``"cn"`` for Chinese. Default is ``"en"``.
        output_dir: Directory to save the report. Defaults to
            ``"./out"``.
        llm_provider: Optional LLM provider for AI analysis.
            ``None`` (default) skips AI analysis. Otherwise, accepts
            common names like ``"deepseek"``, ``"ChatGPT"``,
            ``"Claude"``, ``"qwen"``, etc.

    Returns:
        str: The full report in Markdown format.

    Raises:
        ParameterError: If required parameters (``market``, ``code``)
            are missing.
    """
    return _run_async(
        _async_generate_stock_report(
            market=market, code=code,
            start=start, end=end,
            source=source,
            language=language,
            output_dir=output_dir,
            llm_provider=llm_provider,
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
        language: str = 'en',
        output_dir: Optional[str] = None,
        llm_provider: Optional[str] = None,
) -> str:
    """Async kernel: data fetching runs concurrently via thread pool.

    This function is wrapped by :func:`_generate_stock_report` which
    bridges it back to synchronous callers.
    """
    # ---- validate & prepare ----
    if not market or not code:
        raise ParameterError("Both market and code parameters are required")

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
        _aget_stock_history(market=market, code=code, start=start, end=end),
        _delayed(_aget_stock_realtime(market=market, code=code), 0.3),
        _delayed(_aget_stock_profile(market=market, code=code), 0.6),
        _delayed(_aget_stock_factors(market=market, code=code, trade_date=trade_date), 0.9),
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

        def _fmt_price(val):
            if isinstance(val, (int, float, str)) and str(val).replace('.', '', 1).isdigit():
                return f"${float(val):.2f}"
            return str(val) if val is not None else 'N/A'

        def _fmt_vol(val):
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
            b64 = _get_plot_as_base64(df_history, code, plot_title, plot_ylabel)
            if b64:
                report_sections.extend([
                    f"## {L['title_chart']}",
                    f"![{code} K-Line Chart](data:image/png;base64,{b64})\n",
                ])
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
            import tabulate  # optional
            summary = (
                df_history.select_dtypes(include=['number'])
                .describe()
                .transpose()
            )
            report_sections.append(summary.to_markdown())
        except ImportError:
            report_sections.append(
                L.get('missing_tabulate', '')
                + "\n```text\n"
                + str(df_history.select_dtypes(include=['number']).describe())
                + "\n```"
            )
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
    final_report = "\n".join(report_sections)

    target_dir = output_dir or os.path.join(os.getcwd(), 'out')
    try:
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{code}_report_{today.strftime('%Y%m%d_%H%M%S')}.md"
        file_path = os.path.join(target_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
        logger.info("Report saved to: %s", file_path)
    except Exception as e:
        logger.error("Failed to save report: %s", e)

    return final_report


async def _async_safe_factors(market, code, trade_date) -> Optional[pd.DataFrame]:
    """Fetch factors, tolerating failures gracefully."""
    try:
        return await _aget_stock_factors(market=market, code=code, trade_date=trade_date)
    except Exception as e:
        logger.debug("Factor fetch failed (non-critical): %s", e)
        return None
