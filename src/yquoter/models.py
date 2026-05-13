# yquoter/models.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import pandas as pd
from typing import Optional, Union, Literal, TYPE_CHECKING
from yquoter.logger import get_logger

if TYPE_CHECKING:
    from yquoter.reporting import ReportConfig
from yquoter.exceptions import DataSourceError
from yquoter.datasource import _SOURCE_REGISTRY
from yquoter.plugin_base import DataSource
from yquoter.datasource import (
    _get_stock_history,
    _get_stock_realtime,
    _get_stock_profile,
    _get_stock_financials,
    _get_stock_factors
)
from yquoter.indicators import(
    _get_ma_n,
    _get_rv_n,
    _get_rsi_n,
    _get_boll_n,
    _get_vol_ratio,
    _get_max_drawdown
)
from yquoter.reporting import _generate_stock_report

logger = get_logger(__name__)

class Stock:
    """A class representing a stock for fetching market data and technical indicators.

    Attributes:
        market: Stock exchange market identifier (e.g., 'cn', 'hk', 'us').
        code: Stock ticker/symbol.
        loader: Data source loader name. Default is "spider".
    """

    def __init__(self, market: str, code: str, loader: Optional[Union[str, DataSource]] = None):
        """Initialize a Stock instance.

        Args:
            market: Stock exchange market code. Case-insensitive.
            code: Stock ticker symbol.
            loader: Data source identifier.  Can be a registered source name
                (``str``), a :class:`~yquoter.plugin_base.DataSource`
                instance, or ``None`` to use the global default (see
                :func:`~yquoter.set_default_source`).

        Raises:
            DataSourceError: If a string loader is not registered.
        """
        from yquoter.datasource import _resolve_source

        self.market = market.lower()
        self.code = code

        # Resolve once and cache the DataSource instance so we never
        # re-lookup by name on every method call.
        src = _resolve_source(loader)
        self.loader = src.name
        self._source_instance = src

    def __repr__(self):
        """Return unambiguous string representation of the Stock object."""
        return f"Stock(market={self.market}, code={self.code})"

    def get_history(self,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    klt: Union[str, int] = 101,
                    fqt: int = 1,
                    fields: Literal["basic", "full"] = "basic") -> pd.DataFrame:
        """Fetch historical price/volume (OHLCV) data.

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format. If ``None``,
                fetches from the earliest available date.
            end_date: End date in ``YYYY-MM-DD`` format. If ``None``,
                fetches to the most recent date.
            klt: K-line type (timeframe). Accepts integer codes
                (e.g., 101=daily, 102=weekly) or string aliases
                (e.g., "d", "w"). Default is 101 (daily).
            fqt: Forward-adjusted type. 1=adjusted, 2=unadjusted.
                Default is 1.
            fields: Return fields scope. ``"basic"`` for core OHLCV fields,
                ``"full"`` for extended fields. Default is ``"basic"``.

        Returns:
            pd.DataFrame: DataFrame containing historical OHLCV data.
        """
        return _get_stock_history(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            klt=klt,
            fqt=fqt,
            fields=fields,
            source=self._source_instance or self.loader
        )

    def get_realtime(self, fields: Union[str, list[str]] = None) -> pd.DataFrame:
        """Fetch real-time market data.

        Args:
            fields: Single field name or list of fields to retrieve.
                If ``None`` or empty, returns all available fields.

        Returns:
            pd.DataFrame: Real-time trading data (price, volume,
            bid/ask, etc.).
        """
        return _get_stock_realtime(
            market=self.market,
            code=self.code,
            fields=fields,
            source=self._source_instance or self.loader
        )

    def get_profile(self) -> pd.DataFrame:
        """Fetch company profile information.

        Returns:
            pd.DataFrame: Company metadata (name, industry, listing date,
            description, etc.).
        """
        return _get_stock_profile(
            market=self.market,
            code=self.code,
            source=self._source_instance or self.loader
        )

    def get_factors(self, trade_date: str) -> pd.DataFrame:
        """Fetch factor data for a specific trading date.

        Args:
            trade_date: Trading date in ``YYYY-MM-DD`` format.

        Returns:
            pd.DataFrame: Factor metrics (PE, PB, etc.).
        """
        return _get_stock_factors(
            market=self.market,
            code=self.code,
            trade_date=trade_date,
            source=self._source_instance or self.loader
        )

    def get_financials(self,
                       end_day: str,
                       report_type: Literal["CWBB", "LRB", "ZCFZB", "XJLLB", "YJBB"] = "CWBB",
                       limit: int = 12) -> pd.DataFrame:
        """Fetch financial statements.

        Args:
            end_day: Report period end date in ``YYYY-MM-DD`` format.
            report_type: Financial report type. Options:
                - ``"CWBB"``: Consolidated balance sheet
                - ``"LRB"``: Income statement
                - ``"ZCFZB"``: Balance sheet
                - ``"XJLLB"``: Cash flow statement
                - ``"YJBB"``: Earnings report
            limit: Maximum number of historical periods to fetch.
                Default is 12.

        Returns:
            pd.DataFrame: Financial statement data.
        """
        return _get_stock_financials(
            market=self.market,
            code=self.code,
            end_day=end_day,
            report_type=report_type,
            limit=limit,
            source=self._source_instance or self.loader
        )

    def get_ma(self, start_date: str = None, end_date: str = None,
               n: int = 5) -> pd.DataFrame:
        """Calculate N-period Moving Average (MA).

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: Moving average window size. Default is 5.
                Common values: 5, 10, 20 (short-term);
                30, 50, 60 (medium-term); 120, 200, 250 (long-term).

        Returns:
            pd.DataFrame: Original data with an additional ``MA{n}`` column.
        """
        return _get_ma_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )

    def get_rv(self, start_date: str = None, end_date: str = None,
               n: int = 5) -> pd.DataFrame:
        """Calculate N-period rolling volatility (RV).

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: Rolling window size. Default is 5.

        Returns:
            pd.DataFrame: Data with an additional ``RV{n}`` column.
        """
        return _get_rv_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )
    def get_rsi(self, start_date: str = None, end_date: str = None,
                n: int = 5) -> pd.DataFrame:
        """Calculate N-period Relative Strength Index (RSI).

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: RSI calculation window. Default is 5 (14 is the standard).

        Returns:
            pd.DataFrame: Data with an additional ``RSI{n}`` column.
        """
        return _get_rsi_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )

    def get_boll(self, start_date: str = None, end_date: str = None,
                 n: int = 20) -> pd.DataFrame:
        """Calculate N-period Bollinger Bands.

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: Standard deviation calculation window. Default is 20.

        Returns:
            pd.DataFrame: Data with ``upper``, ``mid``, and ``lower``
            band columns.
        """
        return _get_boll_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )

    def get_vol_ratio(self, start_date: str = None, end_date: str = None,
                      n: int = 20) -> pd.DataFrame:
        """Calculate volume ratio relative to N-period average volume.

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: Baseline volume calculation window. Default is 20.

        Returns:
            pd.DataFrame: Data with a ``vol_ratio{n}`` column.
        """
        return _get_vol_ratio(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )

    def get_max_drawdown(self, start_date: str = None, end_date: str = None,
                          n: int = 5) -> dict:
        """Calculate maximum drawdown over the full available period.

        Args:
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.
            n: Lookback period for the calculation. Default is 5.

        Returns:
            dict: Dictionary containing drawdown metrics:
                - ``max_drawdown``: Maximum drawdown value.
                - ``max_drawdown_peak_date``: Date of the peak.
                - ``max_drawdown_peak_price``: Price at the peak.
                - ``max_drawdown_trough_date``: Date of the trough.
                - ``max_drawdown_trough_price``: Price at the trough.
                - ``recovery_success``: Whether full recovery occurred.
                - ``recovery_days``: Days to recover (or ``None``).
                - ``recovery_date``: Recovery date (or ``None``).
        """
        return _get_max_drawdown(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n,
            source=self._source_instance or self.loader,
        )

    def get_report(self,
                    start: Optional[str] = None,
                    end: Optional[str] = None,
                    language: Literal["cn", "en"] = "en",
                    output_dir: Optional[str] = None,
                    llm_provider: Optional[str] = None,
                    config: Optional[ReportConfig] = None) -> str:
        """Generate a comprehensive stock analysis report.

        The report includes company profile, real-time quote, historical
        price chart, and summary statistics.  Set ``llm_provider`` or
        ``config.llm_provider`` to enable AI-powered market analysis.

        Args:
            start: Report start date in ``YYYY-MM-DD`` format.
            end: Report end date in ``YYYY-MM-DD`` format.
            language: Report language. ``"en"`` for English,
                ``"cn"`` for Chinese. Default is ``"en"``.
                **Ignored if *config* is given.**
            output_dir: Directory to save the report file. If ``None``,
                defaults to ``./out``.
                **Ignored if *config* is given.**
            llm_provider: Optional LLM provider for AI analysis.
                **Ignored if *config* is given.**
            config: :class:`~yquoter.reporting.ReportConfig` instance.
                When provided, *language*, *output_dir*, *llm_provider*,
                *output_format*, and *chart_backend* are taken from
                *config*.

        Returns:
            str: Report content in Markdown or HTML format.
        """
        from yquoter.reporting import _generate_stock_report, ReportConfig as _RC

        if config is not None:
            return _generate_stock_report(
                market=self.market,
                code=self.code,
                start=start,
                end=end,
                source=self._source_instance or self.loader,
                config=config,
            )
        else:
            return _generate_stock_report(
                market=self.market,
                code=self.code,
                start=start,
                end=end,
                source=self._source_instance or self.loader,
                language=language,
                output_dir=output_dir,
                llm_provider=llm_provider,
            )