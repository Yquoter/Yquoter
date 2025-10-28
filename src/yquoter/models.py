# yquoter/models.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import pandas as pd
from typing import Optional, Union, Literal
from yquoter.logger import get_logger
from yquoter.exceptions import DataSourceError
from yquoter.datasource import _SOURCE_REGISTRY
from yquoter.datasource import get_stock_history, get_stock_realtime, get_stock_profile, get_stock_financials, get_stock_factors
from yquoter.indicators import get_ma_n, get_rv_n, get_rsi_n, get_boll_n, get_vol_ratio, get_max_drawdown
from yquoter.reporting import generate_stock_report

logger = get_logger(__name__)

class Stock:
    """A class representing a stock with methods to fetch market data and technical indicators.

    Attributes:
        market (str): Stock exchange market identifier (e.g., 'sh' for Shanghai, 'sz' for Shenzhen).
        code (str): Stock ticker/symbol.
        loader (str): Data source loader name (default: "spider").
    """

    def __init__(self, market: str, code: str, loader: str = "spider"):
        """Initialize a Stock instance.

        Args:
            market: Stock exchange market code (case-insensitive).
            code: Stock ticker symbol.
            loader: Data source identifier. Must be registered in _SOURCE_REGISTRY.

        Raises:
            DataSourceError: If specified loader is not registered.
        """
        self.market = market.lower()
        self.code = code
        if loader in _SOURCE_REGISTRY:
            self.loader = loader
        else:
            raise DataSourceError(f"Unknown data source: {loader}; available sources: {list(_SOURCE_REGISTRY)}")

    def __repr__(self):
        """Return unambiguous string representation of the Stock object."""
        return f"Stock(market={self.market}, code={self.code})"

    def get_history(self,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    klt: Union[str, int] = 101,
                    fqt: int = 1,
                    fields: Literal["basic", "full"] = "basic") -> pd.DataFrame:
        """Fetch historical price/volume data.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format. If None, fetches from earliest available.
            end_date: End date in 'YYYY-MM-DD' format. If None, fetches to most recent.
            klt: K-line type (timeframe). 101=1 minute, 102=5 minutes, etc.
            fqt: Forward-adjusted type (1=adjusted, 2=unadjusted).
            fields: Return fields scope ('basic' for core fields, 'full' for extended).

        Returns:
            DataFrame containing historical OHLCV data.
        """
        return get_stock_history(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            klt=klt,
            fqt=fqt,
            fields=fields,
            source=self.loader
        )

    def get_realtime(self, fields: Union[str, list[str]] = None) -> pd.DataFrame:
        """Fetch real-time market data.

        Args:
            fields: Single field name or list of fields to retrieve. Empty list returns all fields.

        Returns:
            DataFrame with current trading data (price, volume, bid/ask, etc.).
        """
        return get_stock_realtime(
            market=self.market,
            code=self.code,
            fields=fields,
            source=self.loader
        )

    def get_profile(self) -> pd.DataFrame:
        """Fetch company profile information.

        Returns:
            DataFrame containing company metadata (industry, listing date, etc.).
        """
        return get_stock_profile(
            market=self.market,
            code=self.code,
            source=self.loader
        )

    def get_factors(self, trade_date: str) -> pd.DataFrame:
        """Fetch factor data for specific trading date.

        Args:
            trade_date: Date in 'YYYY-MM-DD' format.

        Returns:
            DataFrame containing factor metrics (PE, PB, etc.).
        """
        return get_stock_factors(
            market=self.market,
            code=self.code,
            trade_date=trade_date,
            source=self.loader
        )

    def get_financials(self,
                       end_day: str,
                       report_type: Literal["CWBB", "LRB", "ZCFZB", "XJLLB", "YJBB"] = 'CWBB',
                       limit: int = 12) -> pd.DataFrame:
        """Fetch financial statements.

        Args:
            end_day: Report period end date in 'YYYY-MM-DD' format.
            report_type: Financial report type:
                - 'CWBB': Consolidated balance sheet
                - 'LRB': Income statement
                - 'ZCFZB': Balance sheet
                - 'XJLLB': Cash flow statement
                - 'YJBB': Earnings report
            limit: Maximum number of historical periods to fetch.

        Returns:
            DataFrame containing financial statement data.
        """
        return get_stock_financials(
            market=self.market,
            code=self.code,
            end_day=end_day,
            report_type=report_type,
            limit=limit,
            source=self.loader
        )

    def get_ma(self, start_date: str = None, end_date: str = None, n: int = 5) -> pd.DataFrame:
        """Calculate moving average over n periods.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.
            n: Moving average window size (default 5).
                Common values:
                - Short-term: 5, 10, 20
                - Medium-term: 30, 50, 60
                - Long-term: 120, 200, 250

        Returns:
            DataFrame with MA_n column added.
        """
        return get_ma_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )

    def get_rv(self, start_date: str = None, end_date: str = None, n: int = 5) -> pd.DataFrame:
        """
        Calculate n-period rolling volatility

            Args:
                start_date: Start date
                end_date: End date
                n: Number of periods for calculation (default: 5)

            Returns:
                DataFrame containing dates and corresponding rolling volatility values
        """
        return get_rv_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )
    def get_rsi(self, start_date: str = None, end_date: str = None, n: int = 5) -> pd.DataFrame:
        """Calculate Relative Strength Index (RSI) over n periods.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.
            n: RSI calculation window (default 14 is standard).

        Returns:
            DataFrame with RSI_n column added.
        """
        return get_rsi_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )

    def get_boll(self, start_date: str = None, end_date: str = None, n: int = 20) -> pd.DataFrame:
        """Calculate Bollinger Bands with n-period moving average.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.
            n: Standard deviation calculation window (default 20).

        Returns:
            DataFrame with Upper/Lower Band columns added.
        """
        return get_boll_n(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )

    def get_vol_ratio(self, start_date: str = None, end_date: str = None, n: int = 20) -> pd.DataFrame:
        """Calculate volume ratio compared to n-period average volume.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.
            n: Baseline volume calculation window (default 20).

        Returns:
            DataFrame with Volume_Ratio column added.
        """
        return get_vol_ratio(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )

    def get_max_drawdown(self, start_date: str = None, end_date: str = None, n: int = 5) -> pd.DataFrame:
        """Calculate maximum drawdown over n periods.

        Args:
            start_date: Start date in 'YYYY-MM-DD' format.
            end_date: End date in 'YYYY-MM-DD' format.
            n: Rolling window size for drawdown calculation.

        Returns:
            DataFrame with Max_Drawdown column added.
        """
        return get_max_drawdown(
            market=self.market,
            code=self.code,
            start=start_date,
            end=end_date,
            n=n
        )

    def generate_report(self,
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        language: Literal["cn", "en"] = 'en',
                        output_dir: Optional[str] = None) -> str:
        """Generate comprehensive stock analysis report.

        Args:
            start: Report start date in 'YYYY-MM-DD' format.
            end: Report end date in 'YYYY-MM-DD' format.
            language: Report language ('en' for English, 'cn' for Chinese).
            output_dir: Directory path to save report. If None, returns DataFrame only.

        Returns:
            DataFrame containing report data (may also save to file).
        """
        return generate_stock_report(
            market=self.market,
            code=self.code,
            start=start,
            end=end,
            language=language,
            output_dir=output_dir
        )