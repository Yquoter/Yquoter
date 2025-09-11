# yquoter/spider_source.py

import pandas as pd
import time
from yquoter.spider_core import crawl_kline_segments
from yquoter.utils import *

def get_stock_daily_spider(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1
) -> pd.DataFrame:
    """统一 spider 接口，支持各市场历史数据抓取。"""
    market = market.lower()
    if market == "cn":
        return _get_cn_spider(code, start, end, klt, fqt)
    elif market == "hk":
        return _get_hk_spider(code, start, end, klt, fqt)
    elif market == "us":
        return _get_us_spider(code, start, end, klt, fqt)
    else:
        raise ValueError(f"未知市场：{market}")


def _get_cn_spider(code: str, start: str, end: str, klt: int, fqt: int) -> pd.DataFrame:
    """
    东方财富 A 股 K 线数据爬虫（使用分页器抽象）

    参数说明：
        code: 股票代码，如 '600519' 表示贵州茅台
        start: 起始日期，格式 'YYYYMMDD'
        end: 结束日期，格式 'YYYYMMDD'
        klt: K线类型（101=1分钟, 102=5分钟, 103=15分钟, 104=30分钟,
                      105=60分钟, 1=日K, 2=周K, 3=月K）
        fqt: 复权类型（0=不复权，1=前复权，2=后复权）

    返回：
        包含 ['date', 'open', 'low', 'high', 'close', 'volume'] 的 DataFrame
    """

    # 根据股票代码前缀判断是上交所还是深交所，构造东方财富 API 使用的 secid
    if code.startswith(("600", "601", "603", "605")):
        secid = f"1.{code}"  # 上交所
    elif code.startswith(("000", "001", "002", "003", "300", "301")):
        secid = f"0.{code}"  # 深交所
    else:
        raise CodeFormatError("未知A股代码，无法判断市场")

    # 构造获取某一时间区间 K 线数据的请求 URL
    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)  # 当前时间戳用于防止缓存
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"  # 基础字段
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"  # K线字段
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )

    # 将返回的 JSON 数据解析成二维数组（行列表）
    def parse_kline(json_data):
        if not json_data or "data" not in json_data:
            return []
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(',')
            # 调整顺序为：date, open, low, high, close, volume
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5]])
        return rows

    # 使用分页器处理跨日期段抓取、拼接成完整的 DataFrame
    return crawl_kline_segments(start, end, make_url, parse_kline)

def _get_hk_spider(code: str, start: str, end: str, klt: int, fqt: int) -> pd.DataFrame:
    """
    东方财富 港股 K 线数据爬虫（分页）
    说明：secid 格式为 116.{code}，如 '00700' -> '116.00700'
    """
    secid = f"116.{code.zfill(5)}"  # 确保代码五位数，前补零

    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )

    def parse_kline(json_data):
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(',')
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5]])
        return rows

    return crawl_kline_segments(start, end, make_url, parse_kline)


def _get_us_spider(code: str, start: str, end: str, klt: int, fqt: int) -> pd.DataFrame:
    """
    东方财富 美股 K 线数据爬虫（分页）
    说明：secid 格式为 105.{code}，如 'AAPL' -> '105.AAPL'
    """
    secid = f"105.{code.upper()}"  # 美股代码大写标准化

    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )

    def parse_kline(json_data):
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(',')
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5]])
        return rows

    return crawl_kline_segments(start, end, make_url, parse_kline)


