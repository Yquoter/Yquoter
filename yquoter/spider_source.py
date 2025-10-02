# yquoter/spider_source.py
import pandas as pd
import time
from yquoter.spider_core import crawl_kline_segments,crawl_realtime_data
from yquoter.utils import *

def get_stock_history_spider(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1,
) -> pd.DataFrame:
    """统一 spider 接口，支持各市场历史数据抓取。"""
    secid = get_secid_of_eastmoney(market,code)
    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)  # 当前时间戳用于防止缓存
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"  # 基础字段
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"  # K线字段
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )
    def parse_kline(json_data):
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(',')
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5], parts[6], parts[8], parts[10],
                        parts[9], parts[7]])
        return rows
    return crawl_kline_segments(start, end, make_url, parse_kline)
###############################技术面####################################
def get_secid_of_eastmoney(market: str,code: str):
    market = market.lower().strip()
    if market == "cn":
        if code.startswith(("600", "601", "603", "605")):
            secid = f"1.{code}"  # 上交所
        elif code.startswith(("000", "001", "002", "003", "300", "301")):
            secid = f"0.{code}"  # 深交所
        else:
            raise CodeFormatError("未知A股代码，无法判断市场")
    elif market == "hk":
        secid = f"116.{code.zfill(5)}"  # 确保代码五位数，前补零
    elif market == "us":
        secid = f"105.{code.upper()}"  # 美股代码大写标准化
    else:
        raise ValueError(f"未知市场：{market}")
    return secid

#此处修改完还要修改初始化部分
dict_of_eastmoney = {
    "code":"f12",
    "new":"f2",
    "name":"f14"
}

def map_fields_of_eastmoney(fields: list[str])->list[str]:
    result = []
    for field in fields:
        if field in dict_of_eastmoney:
            result.append(dict_of_eastmoney[field])
        else:
            raise ValueError("无效的字段")
    return result

def get_stock_realtime_spider(
    market: str,
    code: str = "",
    field: str = "",
    codes: list[str] = [],
    fields: list[str] = [],
) -> pd.DataFrame:

    # 清洗用户输入的数据并正确初始化
    if code == "" and codes == []:
        raise ValueError("代码或代码列表不可为空")
    if field == "" and fields == []:
        fields = ["code","name","new"]
    if code != "" and code not in codes:
        codes.append(code)

    if field != "" and field not in fields:
        fields.append(field)
    if "code" not in fields:
        fields.insert(0, "code")
    if "name" not in fields:
        fields.insert(1, "name")

    url_fields = map_fields_of_eastmoney(fields)
    def get_fields_number(field: str) -> int:
        return int(field[1:])
    url_fields.sort(key=get_fields_number)

    secids = []
    for percode in codes:
        persecid = get_secid_of_eastmoney(market,percode)
        secids.append(persecid)

    def make_realtime_url() -> str:
        ts = int(time.time() * 1000)
        # 构建URL
        return (
            f"https://push2.eastmoney.com/api/qt/ulist.np/get"
            f"?OSVersion=14.3"
            f"&appVersion=6.3.8"
            f"&fields={",".join(url_fields)}"
            f"&fltt=2"
            f"&plat=Iphone"
            f"&product=EFund"
            f"&secids={','.join(secids)}"
            f"&serverVersion=6.3.6"
            f"&version=6.3.8"
            f"&_={ts}"
        )
    def parse_realtime_data(json_data):
        realtime_data = json_data.get("data", {}).get("diff", [])
        result = []
        for single_data in realtime_data:
            rows = []
            for value in single_data.values():
                rows.append(value)
            result.append(rows)
        return result
    return crawl_realtime_data(make_realtime_url, parse_realtime_data, url_fields, fields, dict_of_eastmoney)

if __name__ == "__main__":
    pd.set_option('display.max_columns', None)
    pd.set_option('display.float_format', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', 100)
    pd.set_option('display.expand_frame_repr', False)
    df = get_stock_history_spider("cn","600519","20241002","20241012")
    print(df)
    df = get_stock_realtime_spider("hk","00700")
    print(df)
