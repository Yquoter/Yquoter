from yquoter import register_source, get_stock_history, get_ma_n
import pandas as pd

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

# 使用自定义数据源
df_cn = get_stock_history("cn", "002475", "2025-09-01", "2025-09-10", freq='d', source='costom', mode="full")
print(df_cn, "\n")
df_cn = get_stock_history("cn", "002475", "2025-09-01", "2025-09-10", freq='d', source='costom', mode="basic")
print(df_cn, "\n")
df_cn = get_ma_n()
print(df_cn, "\n")

