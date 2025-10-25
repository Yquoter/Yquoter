import yquoter as yq

report = yq.generate_stock_report(market="cn", code="600717", language='en')
print(report)