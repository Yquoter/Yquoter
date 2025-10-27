import yquoter as yq

a1= yq.Stock(market="cn", code="600717")
df = a1.get_ma(n=20)
print(df)
df_2 = a1.get_realtime()
print(df_2)