from src.yquoter import init_tushare, get_stock_history

init_tushare()
df_cn_1 = get_stock_history("cn", "600519", "2023-01-01", "2023-06-30", klt="1Y", source="tushare")
print(df_cn_1)