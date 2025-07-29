from yquoter import init_tushare, get_stock_data

init_tushare("61b9be5ca7ac6921a8daefed77c19644ac42c9a574f8b63e54def692")
df_hk = get_stock_data("cn", "300750", "2023-01-01", "2023-06-30")
print(df_hk, "\n")