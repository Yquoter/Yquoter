import pandas as pd
import time
from datetime import datetime, timedelta
from yquoter.utils import parse_date_str, load_file_to_df
from yquoter.datasource import get_stock_data

def calc_pre_date(date,n):
    """
    提前n个交易日计算工具
    """
    input_date = datetime.strptime(date, '%Y%m%d')
    def is_trading_day(date):
        if date.weekday() >= 5:
            return False
        return True
    count = 0
    current_date = input_date - timedelta(days=1)
    while count < n:
        if is_trading_day(current_date):
            count += 1
        current_date -= timedelta(days=1)
    return str(current_date)



def calc_indicator(df=None, market=None, code=None, start=None, end=None, loader=None, indicator_func=None, **kwargs):
    """
    通用指标计算器
    - df: DataFrame 或 文件路径（字符串）
    - market/code/start/end: 如果 df=None，则调用 loader(market, code, start, end)
    - loader: 数据获取函数（默认用 get_stock_data）
    - indicator_func: 实际指标计算逻辑 (df -> df)
    - kwargs: 传给 indicator_func 的参数
    """
    if isinstance(df, str):
        df = load_file_to_df(df)

    if df is None:
        loader = loader or get_stock_data
        if start is None or end is None:
            end = datetime.today().strftime("%Y%m%d")
            start = (datetime.today() - timedelta(days=90)).strftime("%Y%m%d")
        df = loader(market, code, start, end)

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data = data.sort_values('date').reset_index(drop=True)

    # 调用实际指标计算函数
    result = indicator_func(data, **kwargs).copy()
    result['date'] = result['date'].dt.strftime('%Y%m%d')
    return result

#市场交易类指标（反映股价趋势与交易活跃度）

def get_ma_n(market=None, code=None, start=None, end=None, n=5, df=None):
    """
    计算 MA(n) 日均线
    - 输入可为 DataFrame / 文件路径 / market+code+日期区间
    - 默认取最近 3n 天数据
    """
    def _calc_ma(df, n=5):
        ma_col = f"MA{n}"
        df[ma_col] = df['close'].rolling(window=n, min_periods=1).mean().round(2)
        df = df.loc[n:]
        return df[['date', ma_col]].copy()
    return calc_indicator(df=df, market=market, code=code, start=calc_pre_date(start,n), end=end,
                          indicator_func=_calc_ma, n=n)

def get_rsi_n(market=None, code=None,start=None, end=None, n=5, df=None):
    """
    计算n日相对强弱指数
    """
    def _calc_rsi(df, n=5):
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
        return result.loc[n:].copy()
    return calc_indicator(df=df, market=market, code=code, start=calc_pre_date(start,n), end=end,indicator_func=_calc_rsi, n=n)


#测试
if __name__ == "__main__":
    df = get_ma_n("cn","600519","20250108","20250308",5)
    print(df)
    df = get_rsi_n("cn","600519","20250108","20250308",5)
    print(df)
