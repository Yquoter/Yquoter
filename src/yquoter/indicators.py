# yquoter/indicators.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from yquoter.config import get_newest_df_path
from yquoter.exceptions import DataFetchError, DateFormatError
from yquoter.utils import parse_date_str, load_file_to_df
from yquoter.datasource import _get_stock_history
from yquoter.logger import get_logger

logger = get_logger(__name__)

def calc_indicator(df=None, market=None, code=None, start=None, end=None,
                    pre_days=5, loader=None, indicator_func=None, **kwargs) -> pd.DataFrame:
    """Generic indicator calculator supporting multiple data sources.

    Accepts a DataFrame, file path, or fetches data automatically.
    Applies the given indicator function and returns the result.

    Args:
        df: DataFrame or file path (string) containing stock data.
            If ``None``, data will be fetched automatically.
        market: Market identifier. Required if ``df`` is ``None``.
        code: Stock code. Required if ``df`` is ``None``.
        start: Start date for data fetching. Required if ``df`` is
            ``None``.
        end: End date for data fetching. Required if ``df`` is ``None``.
        pre_days: Number of extra days to fetch before the start date
            for warm-up calculation. Default is 5.
        loader: Function to load data. Defaults to
            ``_get_stock_history``.
        indicator_func: The actual indicator calculation function that
            takes a DataFrame and returns a result.
        **kwargs: Additional parameters passed to the indicator function.

    Returns:
        Result of the indicator calculation, typically a
        ``pd.DataFrame`` or ``dict``.
    """
    real_start = None

    # Use most recent cached data if no parameters provided
    if df is None and market is None and code is None and start is None and end is None:
        path = get_newest_df_path()
        logger.info("Using most recent cached data as no parameters provided")
        if "klt101" not in path:
            logger.error("Indicator calculation could not be performed because klt!=101")
            raise ValueError("Indicator calculation could not be performed because klt!=101 in the latest df")
        df = load_file_to_df(path)
        if not df.empty and 'date' in df.columns:
            real_start = df['date'].iloc[0].strftime("%Y%m%d")

    # Load data from file path if provided
    if isinstance(df, str):
        path = df
        df = load_file_to_df(path)
        if not df.empty and 'date' in df.columns:
            real_start = df['date'].iloc[0].strftime("%Y%m%d")
        logger.info(f"Loading data from file: {path}")

    # Fetch data using loader if df still not available
    if df is None:
        if end is None:
            end = datetime.today().strftime("%Y%m%d")

        if start is None:
            real_start = (datetime.today() - timedelta(days=90)).strftime("%Y%m%d")
            input_start = datetime.strptime(real_start, "%Y%m%d") - timedelta(days=20 + pre_days)
        else:
            real_start = parse_date_str(start, "%Y%m%d")
            input_start = datetime.strptime(real_start, '%Y%m%d') - timedelta(days=20 + pre_days)

        loader = loader or _get_stock_history

        df = loader(market, code, input_start.strftime("%Y%m%d"), end, mode="full")
        logger.info(
            f"Fetching data via {loader.__name__} for {market}:{code} (Input Start: {input_start.strftime('%Y%m%d')})")
        if df is None or df.empty:
            raise DataFetchError(
                f"Failed to load data for {market}:{code} from {input_start.strftime('%Y%m%d')} to {end}")

    # Prepare data for calculation
    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date').reset_index(drop=True)

    # If real_start is still not set but start is provided, derive it
    if real_start is None and start is not None:
        real_start = parse_date_str(start, "%Y%m%d")

    # Calculate and format result
    result = indicator_func(data, real_start, **kwargs)
    if isinstance(result, pd.DataFrame):
        result['date'] = result['date'].dt.strftime('%Y%m%d')
    return result


def _get_ma_n(market: str = None, code: str = None, start: str = None,
               end: str = None, n: int = 5,
               df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate N-period Moving Average (MA).

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Number of periods for MA calculation. Default is 5.
        df: Optional DataFrame with stock data. If provided, ``market``,
            ``code``, ``start``, and ``end`` are ignored.

    Returns:
        pd.DataFrame: Data with an ``MA{n}`` column added.
    """

    def _calc_ma(df, real_start=None, n=5) -> pd.DataFrame:
        logger.info(f"Calculating MA{n} indicator")
        df_result = df.copy()
        ma_col = f"MA{n}"
        df_result[ma_col] = df_result['close'].rolling(window=n, min_periods=1).mean().round(2)
        if real_start is not None:
            try:
                df_result = df_result[df_result['date'] >= real_start]
            except DateFormatError as e:
                logger.error(f"Date comparison failed. Ensure 'df_result[\"date\"]' and 'real_start' are comparable types (e.g., datetime or string): {e}")
                pass
        logger.info(f"MA{n} calculation completed for {len(df)} records")
        return df_result.reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start,end=end, pre_days=n,
                          indicator_func=_calc_ma, n=n)

def _get_rsi_n(market: str = None, code: str = None, start: str = None,
                end: str = None, n: int = 5,
                df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate N-period Relative Strength Index (RSI).

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Number of periods for RSI calculation. Default is 5.
        df: Optional DataFrame with stock data.

    Returns:
        pd.DataFrame: Data with an ``RSI{n}`` column.
    """
    def _calc_rsi(df, real_start, n=5) -> pd.DataFrame:
        logger.info(f"Calculating RSI{n} indicator")
        df['change'] = df['close'].diff()  # Current close - previous close
        df['gain'] = df['change'].where(df['change'] > 0, 0)
        df['loss'] = -df['change'].where(df['change'] < 0, 0)
        df['avg_gain'] = df['gain'].rolling(window=n, min_periods=1).mean()
        df['avg_loss'] = df['loss'].rolling(window=n, min_periods=1).mean()

        # Calculate Relative Strength (RS)
        df['rs'] = df['avg_gain'] / df['avg_loss'].replace(0, 0.0001)  # 避免除以0
        # Calculate RSI
        rsi_col = f"RSI{n}"
        df[rsi_col] = 100 - (100 / (1 + df['rs']))
        df[rsi_col] = df[rsi_col].round(2)
        result = df[['date', rsi_col]].copy()
        df.drop(columns=['change', 'gain', 'loss', 'avg_gain', 'avg_loss', 'rs'], inplace=True)
        result = result[result['date'] >= real_start].copy().reset_index(drop=True)
        logger.info(f"RSI{n} calculation completed for {len(result)} records")
        return result
    return calc_indicator(df=df, market=market, code=code, start=start, end=end, pre_days=n,
                          indicator_func=_calc_rsi, n=n)

def _get_boll_n(market: str = None, code: str = None, start: str = None,
                 end: str = None, n: int = 20,
                 df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate N-period Bollinger Bands.

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Standard deviation window. Default is 20.
        df: Optional DataFrame with stock data.

    Returns:
        pd.DataFrame: Data with ``upper``, ``mid``, and ``lower``
            band columns.
    """
    def _calc_boll(df, real_start, n=20) -> pd.DataFrame:
        logger.info(f"Calculating Bollinger Bands with {n}-period window")
        ma_values = df['close'].rolling(window=n, min_periods=1).mean().round(2)
        std_values = df['close'].rolling(window=n, min_periods=1).std().round(2)

        df['upper'] = (ma_values + 2 * std_values).round(2)
        df['lower'] = (ma_values - 2 * std_values).round(2)
        df['mid'] = ma_values

        df = df[df['date'] >= real_start]
        logger.info(f"Bollinger Bands calculation completed for {len(df)} records")

        return df[['date', 'upper', 'mid', 'lower']].copy().reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start, end=end, pre_days=n,
                          indicator_func=_calc_boll, n=n)

def _get_vol_ratio(market: str = None, code: str = None, start: str = None,
                    end: str = None, n: int = 20,
                    df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate volume ratio against N-period average volume.

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Baseline volume window. Default is 20.
        df: Optional DataFrame with stock data.

    Returns:
        pd.DataFrame: Data with a ``vol_ratio{n}`` column.
    """
    def _calc_vol_ratio(df, real_start, n=5) -> pd.DataFrame:
        logger.info(f"Calculating volume ratio with {n}-period average")
        vol_col = f"vol{n}"
        result_col = f"vol_ratio{n}"
        df[vol_col] = df['vol'].rolling(window=n, min_periods=1).mean().round(2)
        df[result_col] = (df['vol']/df[vol_col]).round(2)
        result = df[['date', result_col]].copy()
        result = result[result['date'] >= real_start].copy().reset_index(drop=True)
        logger.info(f"Volume ratio calculation completed for {len(result)} records")
        return result
    return calc_indicator(df=df, market=market, code=code, start=start,end=end,pre_days=n,
                          indicator_func=_calc_vol_ratio, n=n)

def _get_max_drawdown(market: str = None, code: str = None,
                        start: str = None, end: str = None, n: int = 5,
                        df: pd.DataFrame = None) -> dict:
    """Calculate maximum drawdown and recovery metrics.

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Lookback period. Default is 5.
        df: Optional DataFrame with stock data.

    Returns:
        dict: Dictionary containing:
            - ``max_drawdown``: Maximum drawdown value.
            - ``max_drawdown_peak_date``: Date of the peak before
              drawdown.
            - ``max_drawdown_peak_price``: Price at the peak.
            - ``max_drawdown_trough_date``: Date of the trough.
            - ``max_drawdown_trough_price``: Price at the trough.
            - ``recovery_success``: Whether recovery occurred.
            - ``recovery_days``: Days to recover (or ``None``).
            - ``recovery_date``: Recovery date (or ``None``).
    """

    def _calc_max_drawdown(df, real_start, n=5) -> dict:
        logger.info(f"Calculating max drawdown with {n}-period lookback")
        df = df[df['date'] >= real_start].copy()
        df['cum_max'] = df['close'].cummax()
        df['drawdown'] = df['close'] - df['cum_max']
        max_drawdown = df['drawdown'].min()
        trough_idx = df['drawdown'].idxmin()
        peak_idx = df.loc[:trough_idx, 'cum_max'].idxmax()

        # Check recovery status
        post_trough_df = df[trough_idx:].copy()
        recovery_candidates = post_trough_df[post_trough_df['close'] >= df['close'][peak_idx]]
        recovery_success = False
        recovery_days = None
        recovery_date = None
        if not recovery_candidates.empty:
            recovery_success = True
            recovery_date_data = recovery_candidates.loc[recovery_candidates['date'].idxmin()]
            recovery_days = (recovery_date_data['date'] - df['date'][trough_idx]).days
            recovery_date = recovery_date_data['date']

        result = {
            'max_drawdown': float(max_drawdown),
            'max_drawdown_peak_date': str(df['date'][peak_idx].date()),
            'max_drawdown_peak_price': float(df['close'][peak_idx]),
            'max_drawdown_trough_date': str(df['date'][trough_idx].date()),
            'max_drawdown_trough_price': float(df['close'][trough_idx]),
            'recovery_success': bool(recovery_success),
            'recovery_days': int(recovery_days) if recovery_days is not None else None,
            'recovery_date': str(recovery_date.date()) if recovery_date is not None else None,
        }
        logger.info(f"Max drawdown calculation completed.")
        return result
    return calc_indicator(df=df, market=market, code=code, start=start,end=end,pre_days=n,indicator_func=_calc_max_drawdown, n=n)

def _get_rv_n(market: str = None, code: str = None, start: str = None,
               end: str = None, n: int = 5,
               df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate N-period rolling volatility (RV).

    Args:
        market: Market identifier.
        code: Stock code.
        start: Start date in ``YYYYMMDD`` format.
        end: End date in ``YYYYMMDD`` format.
        n: Rolling window size. Default is 5.
        df: Optional DataFrame with stock data.

    Returns:
        pd.DataFrame: Data with an ``RV{n}`` column.
    """
    def _calc_rv_n(df, real_start, n=5) -> pd.DataFrame:
        logger.info(f"Calculating {n}-period rolling volatility")
        # Calculate logarithmic returns
        df["log_change"] = np.log(df['close'] / df['close'].shift(1))
        rv_col = f"RV{n}"
        # Calculate SD ( standard deviation )
        df[rv_col] = df['log_change'].rolling(window=n, min_periods=1).std() * np.sqrt(n)
        df = df[['date', rv_col]].copy()
        result = df[df['date'] >= real_start].copy().reset_index(drop=True)
        logger.info(f"Rolling volatility calculation completed for {len(result)} records")
        return result
    return calc_indicator(df=df, market=market, code=code, start=start, end=end, pre_days=n, indicator_func=_calc_rv_n, n=n)