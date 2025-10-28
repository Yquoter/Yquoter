# yquoter/reporting.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import pandas as pd
from datetime import datetime, timedelta
from yquoter.logger import get_logger
from yquoter.config import LOCALIZATION
from yquoter.exceptions import PlotLibImportError, ParameterError
from yquoter.indicators import _get_ma_n
from typing import Optional

from yquoter.datasource import (
    _get_stock_history,
    _get_stock_realtime,
    _get_stock_profile,
)

logger = get_logger(__name__)

def _get_plot_as_base64(df_history: pd.DataFrame, code: str, title: str, ylabel: str) -> Optional[str]:
    """
    Generate a base64-encoded K-line (candlestick) chart using mplfinance.

    Args:
        df_history: DataFrame containing stock history data (must contain OHLCV columns)
        code: Stock code/ticker for chart title

    Returns:
        Base64-encoded PNG image string if successful, None otherwise
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
        'Microsoft YaHei',  # Windows (微软雅黑)
        'SimHei',  # Windows (黑体)
        'Arial Unicode MS',  # macOS/Linux (if installed)
        'Noto Sans CJK SC',  # Google's Noto Font (Linux/macOS)
        'WenQuanYi Zen Hei',  # Linux (文泉驿)
        'sans-serif'  # Fallback
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
        # Continue without MA rather than failing completely

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
            dpi=100  # Adjust for quality/size balance
        )
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode('utf-8')

    except Exception as e:
        logger.error("Chart generation failed for stock %s: %s", code, str(e))
        return None


def _generate_stock_report(
        market: str,
        code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: Optional[str] = None,
        language: str = 'en',
        output_dir: Optional[str] = None
) -> str:
    """
    Generate a comprehensive stock report containing profile, real-time data, historical summary,
    and an optional price chart visualization.

    Args:
        market: Stock exchange market identifier (e.g., 'SH' for Shanghai)
        code: Stock symbol/ticker
        start: Start date for historical data (YYYYMMDD format)
        end: End date for historical data (YYYYMMDD format)
        source: Data source provider
        language: Report language ('en' or 'cn')
        output_dir: Directory to save the report (defaults to './out')

    Returns:
        String containing the full report in Markdown format

    Raises:
        ValueError: If essential parameters (market/code) are missing
    """
    # Validate required parameters
    if not market or not code:
        raise ParameterError("Both market and code parameters are required")

    # Set default date range if not provided
    today = datetime.now()
    if start is None and end is None:
        start = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        end = datetime.now().strftime('%Y%m%d')
    elif start is None:
        # If only end is provided, default start to 30 days prior
        try:
            end_date = datetime.strptime(end, '%Y%m%d')
        except ValueError:
            end_date = today # Fallback if end date format is bad
        start = (end_date - timedelta(days=30)).strftime('%Y%m%d')
    elif end is None:
        # If only start is provided, default end to today
        end = today.strftime('%Y%m%d')

    # Language configuration
    lang_key = 'cn' if language.lower() == 'cn' else 'en'
    try:
        L = LOCALIZATION[lang_key]
    except KeyError:
        logger.warning(f"Language '{language}' not found, defaulting to English")
        L = LOCALIZATION['en']

    # Data collection
    try:
        df_history = _get_stock_history(market=market, code=code, start=start, end=end, source=source)
        df_realtime = _get_stock_realtime(market=market, code=code)
        profile = _get_stock_profile(market=market, code=code)
    except Exception as e:
        logger.error(f"Failed to fetch stock data: {e}")
        return f"# Error\nFailed to generate report: {str(e)}"

    # Report sections
    report_sections = []

    # 1. Header section
    report_sections.extend([
        f"# {code} ({market.upper()}) {L['title_report']}",
        f"### {L['header_generated']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"### {L['header_history']}: {start} - {end}\n"
    ])

    # 2. Profile section
    report_sections.append(f"## 📄 {L['title_profile']}")
    if not profile.empty:
        p = profile.iloc[0]
        description = p.get('description', p.get('MAIN_BUSINESS', L['no_description']))
        report_sections.extend([
            f"**{L['label_name']}:** {p.get('name', p.get('NAME', 'N/A'))}",
            f"**{L['label_industry']}:** {p.get('industry', p.get('INDUSTRY', 'N/A'))}",
            f"**{L['label_list_date']}:** {p.get('list_date', p.get('LISTING_DATE', 'N/A'))}",
            f"**{L['label_desc']}:** \n> {description}\n"
        ])
    else:
        report_sections.append(L['missing_profile'] + "\n")

    # 3. Realtime data section
    report_sections.append(f"## 📈 {L['title_realtime']}")
    if not df_realtime.empty:
        data = df_realtime.iloc[0]
        # --- Type check before applying numerical formatting ---
        def format_price(val):
            return f"${float(val):.2f}" if isinstance(val, (int, float, str)) and str(val).replace('.', '',1).isdigit() else str(val) if val is not None else 'N/A'

        def format_volume(val):
            return f"{float(val):,.0f}" if isinstance(val, (int, float, str)) and str(val).replace('.', '',1).isdigit() else str(val) if val is not None else 'N/A'

        latest_price = format_price(data.get('close', 'N/A'))
        open_price = format_price(data.get('open', 'N/A'))
        high_price = format_price(data.get('high', 'N/A'))
        low_price = format_price(data.get('low', 'N/A'))
        volume = format_volume(data.get('vol', 'N/A'))

        report_sections.extend([
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| {L['label_latest_price']} | {latest_price} |",
            f"| {L['label_open']} | {open_price} |",
            f"| {L['label_high']} | {high_price} |",
            f"| {L['label_low']} | {low_price} |",
            f"| {L['label_volume']} | {volume} |\n"
        ])
    else:
        report_sections.append(L['missing_realtime'] + "\n")

    # 4. Chart section
    plot_title = f'{code} {L["title_chart"]}'
    plot_ylabel = f'{L["price_unit"]} '

    try:
        base64_img = _get_plot_as_base64(df_history, code, plot_title, plot_ylabel)
        if base64_img:
            report_sections.extend([
                f"## 📊 {L['title_chart']}",
                f"![{code} K-Line Chart](data:image/png;base64,{base64_img})\n"
            ])
        else:
            report_sections.extend([
                f"## 📊 {L['chart_unavailable']}",
                L['chart_note'] + "\n"
            ])
    except Exception as e:
        logger.error(f"Failed to generate chart: {e}")
        report_sections.extend([
            f"## 📊 {L['chart_unavailable']}",
            L['chart_note'] + "\n"
        ])

    # 5. Historical data summary
    report_sections.append(f"## 📜 {L['title_summary']}")
    if not df_history.empty:
        try:
            # Select numerical columns only for describe, then transpose for better Markdown table
            # Check if tabulate is installed before using to_markdown
            if pd.__version__ >= '1.0.0':  # to_markdown requires a recent pandas version
                try:
                    import tabulate  # Check for optional dependency
                    summary = df_history.select_dtypes(include=['number']).describe().transpose()
                    report_sections.append(summary.to_markdown())
                except ImportError:
                    # Fallback to simple string if tabulate is missing
                    report_sections.append(L['missing_tabulate'] + "\n```text\n" + str(df_history.select_dtypes(include=['number']).describe()) + "\n```")
            else:
                 report_sections.append(L['missing_tabulate'] + "\n```text\n" + str(df_history.select_dtypes(include=['number']).describe()) + "\n```")
        except Exception as e:
            logger.error(f"Failed to generate historical summary: {e}")
            report_sections.append(L['missing_history'])
    else:
        report_sections.append(L['missing_history'])

    # Compile final report
    final_report = "\n".join(report_sections)

    # Save to file
    target_dir = output_dir or os.path.join(os.getcwd(), 'out')
    try:
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{code}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        file_path = os.path.join(target_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
        logger.info(f"Report saved to: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    return final_report