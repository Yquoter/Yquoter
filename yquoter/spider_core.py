# yquoter/spider_core.py

import time
import requests
from datetime import datetime, timedelta
import pandas as pd
from typing import Callable, Optional, Dict, List

def crawl_kline_segments(
    start_date: str,
    end_date: str,
    make_url: Callable[[str, str], str],
    parse_kline: Callable[[Dict], List[List[str]]],
    sleep_seconds: float = 1.0,
    segment_days: int = 365,
) -> pd.DataFrame:
    """
    通用分页 K 线数据爬虫函数，适用于按时间段构造 URL 抓取数据的情形。

    参数说明：
    - start_date (str): 起始日期（格式为 "YYYYMMDD"）
    - end_date (str): 截止日期（格式为 "YYYYMMDD"）
    - make_url (Callable): 接收两个日期字符串（beg, end），返回构造好的请求 URL 的函数
    - parse_kline (Callable): 接收接口返回的 JSON 数据，返回 K 线数据的二维数组（字符串形式）
    - sleep_seconds (float): 每段请求间隔时间，防止触发反爬，默认 1 秒
    - segment_days (int): 每个请求时间段跨度的天数，默认一年（365 天）
    - mode(str): df展开形式
    返回值：
    - pd.DataFrame: 包含日期、开盘、最高、最低、收盘、成交量的标准 K 线数据表
    """
    # 将输入日期字符串转换为 datetime 对象
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    current_dt = start_dt
    all_data = []

    # 设置请求头，避免被识别为爬虫
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }

    # 循环请求，每次获取一个时间段的数据
    while current_dt <= end_dt:
        seg_end = min(current_dt + timedelta(days=segment_days), end_dt)
        beg_str = current_dt.strftime('%Y%m%d')
        end_str = seg_end.strftime('%Y%m%d')

        # 构造 URL
        url = make_url(beg_str, end_str)
        try:
            # 发起请求
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()  # 若 HTTP 状态码异常会抛出异常
            data = resp.json()       # 解析 JSON 格式的响应体

            # 使用外部提供的函数解析数据
            rows = parse_kline(data)
            if rows:
                all_data.extend(rows)
                print(f"成功获取数据：{beg_str} 至 {end_str}，共 {len(rows)} 行")
            else:
                print(f"无数据：{beg_str} 至 {end_str}")
        except Exception as e:
            print(f"请求异常：{e}")

        # 移动时间窗口
        current_dt = seg_end + timedelta(days=1)
        # 等待一段时间，防止被封 IP
        time.sleep(sleep_seconds)

    if not all_data:
        print("未获取到任何数据")
        return pd.DataFrame()

    # 构建 DataFrame，并将数值列转换为浮点型
    df = pd.DataFrame(all_data, columns=["date", "open", "high", "low", "close", "volume", "amount", "change%", "turnover%", "change", "amplitude%"])
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")  # 转换失败时设为 NaN

    return df


def crawl_realtime_data(
    make_url: Callable,
    parse_realtime_data: Callable[[Dict], List[List[str]]],
    url_fields: List[str],
    user_fields: List[str],
    column_map: Dict[str, str],
)->pd.DataFrame:
    result=[]
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    url = make_url()
    try:
        # 发起请求
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()  # 若 HTTP 状态码异常会抛出异常
        data = resp.json()  # 解析 JSON 格式的响应体
        # 解析数据
        result = parse_realtime_data(data)
        if result:
            print(f"成功获取数据：共 {len(result)} 行")
        else:
            print("无数据")
    except Exception as e:
        print(f"请求异常：{e}")
    if not result:
        print("未获取到任何数据")
        return pd.DataFrame()
    df = pd.DataFrame(result,columns=url_fields)
    reverse_map = {v: k for k, v in column_map.items()}
    df.rename(columns=reverse_map, inplace=True)
    df = df[user_fields]
    return df