from yquoter import register_source, get_stock_history, get_ma_n, get_rsi_n, get_boll_n, get_vol_ratio, \
    get_max_drawdown, get_rv_n
import pandas as pd

from yquoter.spider_source import get_stock_realtime_spider
from yquoter.spider_source import get_stock_history_spider


# 定义一个自定义数据源函数
def costom(market, code, start, end, klt=101, fqt=1):
    # 演示，返回一个空 DataFrame
    return pd.DataFrame({
        "date": [start, end],
        "open": [100, 110],
        "high": [105, 115],
        "low": [95, 108],
        "close": [102, 112],
        "volume": [1000, 1200],
        "amount": [1000, 1200],
        "change%": [-5, 5],
        "turnover%": [0, 1],
        "change": [0, 1],
        "amplitude%": [0, 1],
    })


# 注册数据源
register_source("costom", costom)

#df输出格式设置
pd.set_option('display.max_columns', None)
pd.set_option('display.float_format', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', 100)
pd.set_option('display.expand_frame_repr', False)

# 使用自定义数据源

df_cn = get_stock_history("cn", "002475", "2025-09-01", "2025-09-10", freq='d', source='costom', fields="full")
print(df_cn, "\n")
df_cn = get_stock_history("cn", "002475", "2025-09-01", "2025-09-10", freq='d', source='costom', fields="basic")
print(df_cn, "\n")
df_cn = get_ma_n()
print(df_cn, "\n")

#实时行情爬虫测试集
df_realtime = get_stock_realtime_spider(market="cn", codes=["600519"])
print(df_realtime, "\n")
df_realtime = get_stock_realtime_spider(market="us", codes="AAPL", fields=["code", "open", "pre_close"])
print(df_realtime, "\n")

#历史行情爬虫测试集

df = get_stock_history_spider("cn", "600519", "20241002", "20241012")
print(df, "\n")

#指标计算测试集
df = get_ma_n("cn", "600519", "20241002", "20241012", 5)
print(df, "\n")
df = get_rsi_n("cn", "600519", "20250108", "20250204", 5)
print(df, "\n")
df = get_boll_n("cn", "600519", "20241002", "20241012", 20)
print(df, "\n")
df = get_vol_ratio("cn", "600519", "20250108", "20250206", 5)
print(df, "\n")
df = get_stock_history("cn", "600519", "20250128", "20250209")
print(df, "\n")
drawdown = get_max_drawdown("cn", "600519", "20250825", "20250911")
print(drawdown, "\n")
df = get_rv_n("cn", "600519", "20250108", "20250119", 5)
print(df, "\n")
