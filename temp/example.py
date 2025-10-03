from yquoter import init_tushare, get_stock_history
init_tushare("your_token")
df_cn = get_stock_history("cn", "600519", "2023-01-01", "2023-06-30")
df_hk = get_stock_history("hk", "00700", "2023-01-01", "2023-06-30")
df_us = get_stock_history("us", "AAPL", "2023-01-01", "2023-06-30")
