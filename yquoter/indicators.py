import pandas as pd
import time
from datetime import datetime, timedelta
from yquoter.utils import parse_date_str, load_file_to_df
from yquoter.datasource import get_stock_data

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

def get_ma_n(market=None, code=None, start=None, end=None, n=5, df=None):
    """
    计算 MA(n) 日均线
    - 输入可为 DataFrame / 文件路径 / market+code+日期区间
    - 默认取最近 3n 天数据
    """
    def _calc_ma(df, n=5):
        ma_col = f"MA{n}"
        df[ma_col] = df['close'].rolling(window=n, min_periods=1).mean().round(2)
        return df[['date', ma_col]].copy()
    return calc_indicator(df=df, market=market, code=code, start=start, end=end,
                          indicator_func=_calc_ma, n=n)

#测试
if __name__ == "__main__":
    df = get_ma_n("cn","600519","20250108","20250308",5)
    print(df)
