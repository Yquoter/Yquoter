import pandas as pd
import requests
import io
from datetime import datetime

def convert_code_for_163(code: str) -> str:
    """
    将 A 股代码转为网易财经接口使用的格式：
    沪市前缀 0，深市前缀 1
    """
    if code.startswith('6'):
        return '0' + code
    elif code.startswith('0') or code.startswith('3'):
        return '1' + code
    else:
        raise ValueError(f"无法识别的 A 股代码格式：{code}")
    
def _build_url_163(code: str, start: str, end: str) -> str:
    """
    构造一个网易财经历史数据 CSV 下载链接
    """
    prefix_code = convert_code_for_163(code)

    start_fmt = datetime.strptime(start, "%Y-%m-%d").strftime("%Y%m%d")
    end_fmt = datetime.strptime(end, "%Y-%m-%d").strftime("%Y%m%d")

    url = f"http://quotes.money.163.com/service/chddata.html?code={prefix_code}&start={start_fmt}&end={end_fmt}&fields=TCLOSE;HIGH;LOW;TOPEN;VOTURNOVER;CHG"
    return url

def _fetch_china_stock(code: str, start: str, end: str) -> bytes:
    """
    从网易财经抓取原始 A 股 CSV 数据（二进制形式）
    """
    url = _build_url_163(code, start, end)
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"请求失败，状态码：{response.status_code}")
    
def _parse_csv_to_df(csv_bytes: bytes) -> pd.DataFrame:
    """
    将网易财经返回的原始 CSV 字节流解析为 pandas DataFrame
    """
    sio = io.StringIO(csv_bytes.decode("gbk"))
    df = pd.read_csv(sio)

    print(df.columns)  # 临时查看列名
    return df

if __name__ == "__main__":
    code = "600519"  # 茅台
    start = "2023-01-01"
    end = "2023-06-30"

    # 第一步：抓原始 CSV 字节流
    raw_bytes = _fetch_china_stock(code, start, end)

    # 第二步：解析为 DataFrame
    df = _parse_csv_to_df(raw_bytes)

    # 查看前几行
    print(df.head())
