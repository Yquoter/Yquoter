import os
import pandas as pd
from typing import Optional
from yquoter.logger import get_logger
from yquoter.config import get_cache_root  # 导入缓存根目录

# ---------- 日志配置 ----------
logger = get_logger(__name__)

def get_cache_path(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int,
    fqt: int,
    cache_root: Optional[str] = None
) -> str:
    """
    根据市场、代码和时间区间生成缓存文件路径
    """
    root = cache_root or get_cache_root()
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")
    folder = os.path.join(root, market.lower(), code)
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        logger.error(f"创建缓存目录失败: {folder}，异常: {e}")
        raise
    filename = f"{start_fmt}_{end_fmt}_klt{klt}_fqt{fqt}.csv"
    path = os.path.join(folder, filename)
    logger.debug(f"生成缓存路径: {path}")
    return path

def cache_exists(path: str) -> bool:
    """
    判断指定路径缓存文件是否存在
    """
    exists = os.path.isfile(path)
    logger.debug(f"缓存文件 {'存在' if exists else '不存在'}: {path}")
    return exists

def load_cache(path: str) -> Optional[pd.DataFrame]:
    """
    从缓存文件读取数据为 DataFrame，读取失败返回 None
    """
    if not cache_exists(path):
        logger.info(f"缓存文件不存在，无法加载: {path}")
        return None
    try:
        df = pd.read_csv(path)
        if df.empty:
            logger.warning(f"缓存文件内容为空: {path}")
            return None
        logger.info(f"成功加载缓存文件: {path}")
        return df
    except Exception as e:
        logger.error(f"加载缓存文件失败: {path}，异常: {e}")
        return None

def save_cache(path: str, df: pd.DataFrame):
    """
    将 DataFrame 保存到缓存文件
    """
    try:
        df.to_csv(path, index=False)
        logger.info(f"成功保存缓存文件: {path}")
    except Exception as e:
        logger.error(f"保存缓存文件失败: {path}，异常: {e}")
        raise