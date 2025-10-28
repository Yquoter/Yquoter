import yquoter as yq

df = yq.get_newest_df_path()
print(df)

df_s = yq.get_stock_history(market="cn", code="600797")
print(df_s)