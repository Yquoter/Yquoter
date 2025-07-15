import requests
import pandas as pd
import random
from datetime import datetime, timedelta
import time

def get_stock_history_spider(stock_code, start_date, end_date, klt=101, fqt=1):
        """
        undo: klt & fgt
        tag: 获取东方财富网股票  A股   历史行情数据    
        args:   stock_code: 股票代码，如'300195'
                start_date: 开始日期，格式'YYYYMMDD'
                end_date: 结束日期，格式'YYYYMMDD'
                klt: K线周期，101=日线，102=周线，103=月线
                fqt: 复权类型，0=不复权，1=前复权，2=后复权
        return: a dataframe
        
        """
        #确定secid（根据股票代码判断市场）
        if stock_code.startswith(('600', '601', '603', '605')):  # 沪市
            secid = f"1.{stock_code}"
        elif stock_code.startswith(('000', '001', '002', '003', '300', '301')):  # 深市（含创业板）
            secid = f"0.{stock_code}"
        else:
            print("未知市场的股票代码")
            return None
    
        #处理日期范围
        all_data = []
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        segment_size = timedelta(days=365)
        current_start = start
        
        while current_start <= end:
            #这个while的作用是分段获取数据
            current_end = min(current_start + segment_size, end)
            current_start_str = current_start.strftime('%Y%m%d')
            current_end_str = current_end.strftime('%Y%m%d')
        
            #构建接口URL
            timestamp = int(time.time() * 1000)
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}"
                f"&ut=fa5fd1943c7b386f1734de82599f7dc"
                f"&fields1=f1,f2,f3,f4,f5,f6"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
                f"&klt={klt}"#k线周期
                f"&fqt={fqt}"#复权
                f"&beg={current_start_str}"
                f"&end={current_end_str}"
                f"&lmt=10000"
                f"&_={timestamp}"
            )
        
            #发送请求 
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://quote.eastmoney.com/",
            }
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            
                if data.get("data") and data["data"].get("klines"):
                    klines = data["data"]["klines"]
                    columns = ["date","open","high","low","close","volume"]
                    need=[]
                    for line in klines:
                        need.append([line.split(',')[i] for i in [0,1,3,4,2,5]])
                    segment_df = pd.DataFrame(
                        need,
                        columns=columns
                    )
                    all_data.append(segment_df)
                    print(f"成功获取股票 {stock_code} 从 {current_start_str} 至 {current_end_str} 的数据，共 {len(segment_df)} 行")
                else:
                    print(f"分段请求失败: {data.get('msg', '未知错误')}")
            
                time.sleep(1)
            
            except Exception as e:
                print(f"请求异常: {e}")
                time.sleep(3)        
            current_start = current_end + timedelta(days=1)
        response.close()
        #合并所有分段数据
        if all_data:
            df = pd.concat(all_data, ignore_index=True)
        #转换数据类型（排除日期列）
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        else:
            print("未获取到任何数据")
            return None



