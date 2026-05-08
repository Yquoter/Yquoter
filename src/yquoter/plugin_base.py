# yquoter/plugin_base.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

"""Abstract base class and protocol definitions for Yquoter data source plugins.

All built-in and third-party data sources inherit from :class:`DataSource`
to provide a unified interface for stock market data retrieval.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Set, Union
import asyncio

import pandas as pd

from yquoter.exceptions import DataSourceError


class DataSource(ABC):
    """Abstract base class for Yquoter data source plugins.

    Each plugin provides market data for one or more function types
    (history, realtime, financials, profile, factors).  Plugins declare
    their capabilities via properties and implement the corresponding
    methods.

    Built-in implementations:

    * :class:`~yquoter.spider_source.SpiderDataSource` -- Eastmoney spider
    * :class:`~yquoter.tushare_source.TushareDataSource` -- TuShare Pro API

    Example for a third-party plugin::

        from yquoter.plugin_base import DataSource

        class MySource(DataSource):
            name = "my_source"
            supported_types = {"history", "realtime"}

            def get_history(self, market, code, start, end, **kwargs):
                # ...
                return pd.DataFrame()
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique lowercase identifier for this source (e.g., ``"spider"``)."""
        ...

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def supported_types(self) -> Set[str]:
        """Set of function types this source implements.

        Valid values: ``"history"``, ``"realtime"``, ``"financials"``,
        ``"profile"``, ``"factors"``.
        """
        return set()

    @property
    def supports_batch_realtime(self) -> bool:
        """Whether ``get_realtime()`` accepts a list of codes.

        ``True`` (default) -- the dispatch layer passes ``code: List[str]``.

        ``False`` -- the dispatch layer iterates single codes and calls
        ``get_realtime()`` with ``code: str`` each time.  Required for
        sources whose API only accepts one code per request.
        """
        return True

    @property
    def initialization_hint(self) -> Optional[str]:
        """Message shown when this source name is recognised but not yet
        registered (e.g., ``"Use yquoter.init_tushare(token) to enable."``).
        """
        return None

    # ------------------------------------------------------------------
    # Synchronous API  (override to implement)
    # ------------------------------------------------------------------

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
        """Fetch historical OHLCV K-line data.

        Args:
            market: Market identifier (``"cn"``, ``"hk"``, ``"us"``).
            code: Stock ticker symbol.
            start: Start date in ``YYYYMMDD`` format.
            end: End date in ``YYYYMMDD`` format.
            klt: K-line type code.  Default 101 (daily).
            fqt: Forward-adjustment type.  Default 1 (adjusted).
            **kwargs: Source-specific extra parameters.

        Returns:
            DataFrame with columns ``date``, ``open``, ``high``, ``low``,
            ``close``, ``vol``, ``amount``, etc.

        Raises:
            DataSourceError: If this source does not support history data.
        """
        raise DataSourceError(
            f"Data source '{self.name}' does not support history data."
        )

    def get_realtime(
        self,
        market: str,
        code: Union[str, List[str]],
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch real-time quotes.

        .. note::

           When :attr:`supports_batch_realtime` is ``True``, ``code`` is
           a ``List[str]``.  When ``False``, it is a single ``str``.

        Args:
            market: Market identifier.
            code: Single stock code or list of codes.
            fields: Desired data fields.
            **kwargs: Source-specific extra parameters.

        Returns:
            DataFrame with real-time quote data.

        Raises:
            DataSourceError: If this source does not support realtime data.
        """
        raise DataSourceError(
            f"Data source '{self.name}' does not support realtime data."
        )

    def get_financials(
        self,
        market: str,
        code: str,
        end_day: str,
        report_type: str = "CWBB",
        limit: int = 12,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch financial statements.

        Args:
            market: Market identifier.
            code: Stock ticker symbol.
            end_day: Latest report period end date in ``YYYYMMDD`` format.
            report_type: Report type (``"CWBB"``, ``"LRB"``, etc.).
            limit: Number of recent periods to fetch.
            **kwargs: Source-specific extra parameters.

        Returns:
            DataFrame with financial statement data.

        Raises:
            DataSourceError: If this source does not support financials data.
        """
        raise DataSourceError(
            f"Data source '{self.name}' does not support financials data."
        )

    def get_profile(
        self,
        market: str,
        code: str,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch company profile information.

        Args:
            market: Market identifier.
            code: Stock ticker symbol.
            **kwargs: Source-specific extra parameters.

        Returns:
            DataFrame with company metadata (name, industry, listing date).

        Raises:
            DataSourceError: If this source does not support profile data.
        """
        raise DataSourceError(
            f"Data source '{self.name}' does not support profile data."
        )

    def get_factors(
        self,
        market: str,
        code: str,
        trade_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch valuation / market factor data.

        Args:
            market: Market identifier.
            code: Stock ticker symbol.
            trade_date: Trading date in ``YYYYMMDD`` format.
            **kwargs: Source-specific extra parameters.

        Returns:
            DataFrame with factor metrics (PE, PB, etc.).

        Raises:
            DataSourceError: If this source does not support factors data.
        """
        raise DataSourceError(
            f"Data source '{self.name}' does not support factors data."
        )

    # ------------------------------------------------------------------
    # Asynchronous API  (override for native async)
    # ------------------------------------------------------------------
    #
    # The default implementation wraps the sync method in a thread-pool
    # executor so that even purely synchronous sources (e.g. TuShare) work
    # in async contexts without modification.
    # ------------------------------------------------------------------

    async def get_history_async(
        self,
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int = 101,
        fqt: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        """Async variant of :meth:`get_history`."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.get_history(
                market, code, start, end, klt=klt, fqt=fqt, **kwargs,
            ),
        )

    async def get_realtime_async(
        self,
        market: str,
        code: Union[str, List[str]],
        fields: Optional[Union[str, List[str]]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Async variant of :meth:`get_realtime`."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.get_realtime(market, code, fields=fields, **kwargs),
        )

    async def get_profile_async(
        self,
        market: str,
        code: str,
        **kwargs,
    ) -> pd.DataFrame:
        """Async variant of :meth:`get_profile`."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.get_profile(market, code, **kwargs),
        )

    async def get_factors_async(
        self,
        market: str,
        code: str,
        trade_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        """Async variant of :meth:`get_factors`."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.get_factors(market, code, trade_date, **kwargs),
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
