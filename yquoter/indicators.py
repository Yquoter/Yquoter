from unittest import result
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from yquoter.config import get_newest_df_path
from yquoter.utils import parse_date_str, load_file_to_df
from yquoter.datasource import get_stock_history

def calc_indicator(df=None, market=None, code=None, start=None, end=None,pre_days=5, loader=None, indicator_func=None, **kwargs):
    """
    通用指标计算器
    - df: DataFrame 或 文件路径（字符串）
    - market/code/start/end: 如果 df=None，则调用 loader(market, code, start, end)
    - loader: 数据获取函数（默认用 get_stock_history）
    - indicator_func: 实际指标计算逻辑 (df -> df)
    - kwargs: 传给 indicator_func 的参数
    """
    if df is None and market is None and code is None and start is None and end is None:
        df = get_newest_df_path()
    real_start = "YYYYMMDD"
    if isinstance(df, str):
        df = load_file_to_df(df)
        real_start = df['date'].iloc[0].strftime("%Y%m%d")
    if df is None:
        input_start="YYYYMMDD"
        if start is not None:
            real_start = parse_date_str(start, "%Y%m%d")
            input_start = datetime.strptime(start, '%Y%m%d') - timedelta(days=15)
        loader = loader or get_stock_history
        if start is None or end is None:
            end = datetime.today().strftime("%Y%m%d")
            real_start = (datetime.today() - timedelta(days=90)).strftime("%Y%m%d")
            input_start = datetime.strptime(real_start, "%Y%m%d") - timedelta(days=20+pre_days)
        df = loader(market, code, str(input_start), end, mode="full")

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date').reset_index(drop=True)

    # 调用实际指标计算函数
    result = indicator_func(data, real_start, **kwargs)
    if isinstance(result, pd.DataFrame):
        result['date'] = result['date'].dt.strftime('%Y%m%d')
    return result


def get_ma_n(market=None, code=None, start=None, end=None, n=5, df=None):
    """
    计算 MA(n) 日均线
    - 输入可为 DataFrame / 文件路径 / market+code+日期区间
    - 默认取最近 3n 天数据
    """

    def _calc_ma(df, real_start=0, n=5):
        ma_col = f"MA{n}"
        df[ma_col] = df['close'].rolling(window=n, min_periods=1).mean().round(2)
        df = df[df['date'] >= real_start]
        return df[['date', ma_col]].copy().reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start,end=end, pre_days=n,
                          indicator_func=_calc_ma, n=n)

def get_rsi_n(market=None, code=None,start=None, end=None, n=5, df=None):
    """
    计算n日相对强弱指数
    """
    def _calc_rsi(df, real_start, n=5):
        df['change'] = df['close'].diff()  # 今日收盘价-昨日收盘价
        df['gain'] = df['change'].where(df['change'] > 0, 0)
        df['loss'] = -df['change'].where(df['change'] < 0, 0)
        df['avg_gain'] = df['gain'].rolling(window=n, min_periods=1).mean()
        df['avg_loss'] = df['loss'].rolling(window=n, min_periods=1).mean()

        #计算相对强弱RS
        df['rs'] = df['avg_gain'] / df['avg_loss'].replace(0, 0.0001)  # 避免除以0
        #计算RSI
        rsi_col = f"RSI{n}"
        df[rsi_col] = 100 - (100 / (1 + df['rs']))
        df[rsi_col] = df[rsi_col].round(2)
        result = df[['date', rsi_col]].copy()
        df.drop(columns=['change', 'gain', 'loss', 'avg_gain', 'avg_loss', 'rs'], inplace=True)
        return result[result['date'] >= real_start].copy().reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start, end=end, pre_days=n,
                          indicator_func=_calc_rsi, n=n)

def get_boll_n (market=None, code=None, start=None, end=None, n=20, df=None):
    def _calc_boll(df,real_start,n=20):
        ma_col = f"mid{n}"
        df[ma_col] = df['close'].rolling(window=n, min_periods=1).mean().round(2)
        std_col = f"std{n}"
        df[std_col] = df['close'].rolling(window=n, min_periods=1).std().round(2)
        df['up'] = (df[ma_col] + 2 * df[std_col]).round(2)
        df['down'] = (df[ma_col] - 2 * df[std_col]).round(2)
        df = df[df['date'] >= real_start]
        return df[['date','up', ma_col,'down']].copy().reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start,end=end,pre_days=n,
                          indicator_func=_calc_boll, n=n)

def get_vol_ratio(market=None, code=None, start=None, end=None, n=20, df=None):
    def _calc_vol_ratio(df,real_start,n=5):
        vol_col = f"vol{n}"
        result_col = f"vol_ratio{n}"
        df[vol_col] = df['volume'].rolling(window=n, min_periods=1).mean().round(2)
        df[result_col] = (df['volume']/df[vol_col]).round(2)
        result = df[['date', result_col]].copy()
        return result[result['date'] >= real_start].copy().reset_index(drop=True)
    return calc_indicator(df=df, market=market, code=code, start=start,end=end,pre_days=n,
                          indicator_func=_calc_vol_ratio, n=n)

def get_max_drawdown(market=None, code=None, start=None, end=None, n=5, df=None):
    def _calc_max_drawdown(df,real_start,n=5):
        df = df[df['date'] >= real_start].copy()
        df['cum_max'] = df['close'].cummax()
        df['drawdown'] = df['close'] - df['cum_max']
        max_drawdown = df['drawdown'].min()
        trough_idx = df['drawdown'].idxmin()
        peak_idx = df.loc[:trough_idx, 'cum_max'].idxmax()

        #修复检测
        post_trough_df = df[trough_idx:].copy()
        recovery_candidates = post_trough_df[post_trough_df['close'] >= df['close'][peak_idx]]
        recovery_success = False
        recovery_days = None
        recovery_date = None
        if not recovery_candidates.empty:
            recovery_success = True
            recovery_date = recovery_candidates.index[0]
            recovery_days = (df['close'][recovery_date] - df['close'][trough_idx]).days

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
        return result
    return calc_indicator(df=df, market=market, code=code, start=start,end=end,pre_days=n,indicator_func=_calc_max_drawdown, n=n)

def get_rv_n(market=None, code=None, start=None, end=None, n=5, df=None):
    def _calc_rv_n(df,real_start,n=5):
        #计算对数增长率
        df["log_change"] = np.log(df['close'] / df['close'].shift(1))
        rv_col = f"rv{n}"
        #计算标准差
        df[rv_col] = df['log_change'].rolling(window=n, min_periods=1).std() * np.sqrt(n)
        df = df[['date',rv_col]].copy()
        return df[df['date'] >= real_start].copy()
    return calc_indicator(df=df, market=market, code=code, start=start, end=end, pre_days=n, indicator_func=_calc_rv_n, n=n)

#测试
if __name__ == "__main__":
    df = get_ma_n("cn","600519","20241002","20241012",5)
    print(df)
    df = get_rsi_n("cn","600519","20250108","20250202",5)
    print(df)
    df = get_boll_n("cn","600519","20241002","20241012",20)
    print(df)
    df = get_vol_ratio("cn","600519","20250108","20250202",5)
    print(df)
    df = get_stock_history("cn","600519","20250128","20250209")
    print(df)
    drawdown = get_max_drawdown("cn","600519","20250108","20250202")
    print(drawdown)
    df = get_rv_n("cn","600519","20250108","20250119",5)
    print(df)
