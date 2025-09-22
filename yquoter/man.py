import pandas as pd
import time
from datetime import datetime, timedelta
from yquoter.spider_source import get_stock_daily_spider


def get_ma_n(market,code,start,end,n):
    """
    MA计算
    参数说明：
        market:市场
        code:股票代码
        start:起始日期
        end:结束日期
        n:MA为n日均线
    返回：
        包含['date',f'MA{n}']的dataframe
    """
    try:
        base_date = datetime.strptime(start, "%Y%m%d")
        #把开始日期转换为原本第一天的n天前的日期，以确保可以得到第一天数据
        n_days_ago = base_date - timedelta(days=n)  
    except ValueError:
        return "输入的日期格式不正确，请使用YYYYMMDD格式"

    
    data=get_stock_daily_spider(market,code,n_days_ago.strftime("%Y%m%d"),end)
    data = data.copy()
    
    # 转换YYYYMMDD格式的字符串为datetime
    data['date'] = pd.to_datetime(data['date'], format='%Y-%m-%d')
    data = data.sort_values('date').reset_index(drop=True)
    # 计算MAn均线：使用滚动窗口计算收盘价的平均值
    ma_column = f'MA{n}'
    # min_periods=1表示不足n天也计算（如前4天的MA5用已有数据计算）
    data[ma_column] = data['close'].rolling(window=n, min_periods=1).mean()
    data[ma_column] = data[ma_column].round(2)
    data['date'] = data['date'].dt.strftime('%Y%m%d')
    data = data[data['date']>start]
    result=data[['date',ma_column]]
    #print(result)
    return result
#测试
#get_ma_n("cn","600519","20250108","20250308",5)
