import re
import pandas as pd
from yquoter.logger import get_logger
from datetime import datetime
from typing import Optional, Literal, List
import os
# ---------- 日志配置 ----------
logger = get_logger(__name__)

# ---------- 异常 ----------
class CodeFormatError(ValueError):
    pass

class DateFormatError(ValueError):
    pass

# ---------- 股票代码工具 ----------

def normalize_code(code: str) -> str:
    """去除空白并转大写"""
    return code.strip().upper()

def has_market_suffix(code: str) -> bool:
    """
    判断代码是否带有市场后缀，例如 '600519.SH'、'00700.HK'
    """
    return bool(re.match(r'^[\w\d]+\.([A-Z]{2,3})$', code))

def convert_cn_share_to_tushare(code: str) -> str:
    code = normalize_code(code)
    if has_market_suffix(code):
        return code
    if code.startswith('6'):
        return f"{code}.SH"
    elif code.startswith(('0', '3')):
        return f"{code}.SZ"
    elif code.startswith('9'):
        return f"{code}.BJ"
    raise CodeFormatError(f"无法识别的A股代码格式: {code}")

def convert_hk_share_to_tushare(code: str) -> str:
    code = normalize_code(code)
    if has_market_suffix(code):
        return code
    # 港股一般代码为数字，补全到5位，不足左补0
    code_padded = code.zfill(5)
    return f"{code_padded}.HK"

def convert_us_share_to_tushare(code: str) -> str:
    code = normalize_code(code)
    if has_market_suffix(code):
        return code
    # 美股代码一般全大写字母，无特殊处理
    return f"{code}.US"

def convert_code_to_tushare(
    code: str, 
    market: Literal['cn', 'hk', 'us']
) -> str:
    """
    根据市场类型转换股票代码为TuShare标准格式
    """
    market = market.lower()
    if market == 'cn':
        return convert_cn_share_to_tushare(code)
    elif market == 'hk':
        return convert_hk_share_to_tushare(code)
    elif market == 'us':
        return convert_us_share_to_tushare(code)
    else:
        raise CodeFormatError(f"未知市场类型：{market}")

# ---------- 日期处理工具 ----------

def parse_date_str(
    date_str: str, 
    fmt_out: str = "%Y%m%d"
) -> str:
    """
    解析多种常见日期字符串，输出指定格式字符串。

    支持输入格式示例：
    - '2025-07-09'
    - '2025/07/09'
    - '20250709'
    - '2025-07-09 23:00:00'

    Args:
        date_str: 输入的日期字符串
        fmt_out: 输出格式，默认 'YYYYMMDD'

    Returns:
        格式化后的日期字符串

    Raises:
        DateFormatError: 无法识别日期格式时抛出
    """
    date_str = date_str.strip()
    fmts_in = ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts_in:
        try:
            dt = datetime.strptime(date_str, fmt)
            formatted = dt.strftime(fmt_out)
            logger.debug(f"成功解析日期: {date_str} -> {formatted}")
            return formatted
        except ValueError:
            continue
    logger.error(f"无法识别的日期格式: {date_str}")
    raise DateFormatError(f"无法识别的日期格式: {date_str}")


def load_file_to_df(path: str, **kwargs) -> pd.DataFrame:
    """
    根据文件后缀自动加载为 DataFrame
    支持 csv / xlsx / json / parquet
    额外参数通过 kwargs 传给对应的 pandas 读取函数

    返回：
        pd.DataFrame，包含至少 ['date', 'close'] 列
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")

    ext = os.path.splitext(path)[-1].lower()

    if ext == ".csv":
        df = pd.read_csv(path, **kwargs)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(path, **kwargs)
    elif ext == ".json":
        df = pd.read_json(path, **kwargs)
    elif ext == ".parquet":
        df = pd.read_parquet(path, **kwargs)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    # 标准化字段
    if "date" not in df.columns:
        raise ValueError("数据缺少 'date' 列")
    if "close" not in df.columns:
        raise ValueError("数据缺少 'close' 列")

    # 确保日期列转成 datetime
    df["date"] = pd.to_datetime(df["date"], errors="coerce",format="%Y%m%d")
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    return df

def filter_fields(df: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
    """
        Args:
        df: 数据源返回的 DataFrame
        fields: 用户想要的字段列表

    Returns:
        DataFrame，只包含指定的字段
    """
    if not fields:
        return df
    available = [f for f in fields if f in df.columns]
    missing = [f for f in fields if f not in df.columns]

    if missing:
        print("")

    return df[available]