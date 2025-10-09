from src.yquoter import get_stock_history, get_stock_factors
df_cn_1 = get_stock_history("cn", "600519", "2023-01-01", "2023-06-30", klt="1Y")
print(df_cn_1)
df_2 = get_stock_factors("cn", "600519", "2023-06-30")
print(df_2)