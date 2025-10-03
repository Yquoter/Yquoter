import os
import pandas as pd
from typing import Optional
from yquoter.logger import get_logger
from yquoter.config import get_cache_root, modify_df_path  # 导入缓存根目录


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
        modify_df_path(path)

        # 更新访问计数器
        dir_path = os.path.dirname(path)
        _cache_counter.setdefault(dir_path, 0)
        _cache_counter[dir_path] += 1

        # 执行LRU清理
        _cleanup_cache_directory(dir_path)

    except Exception as e:
        logger.error(f"保存缓存文件失败: {path}，异常: {e}")
        raise


_MAX_CACHE_ENTRIES = 10  # 默认最大缓存条目数
_cache_counter = {}  # 目录级别的访问计数器

# 设置最大缓存条目数
def set_max_cache_entries(max_entries: int):
    """
    设置每个目录的最大缓存文件数量

    参数:
        max_entries: 每个目录允许的最大缓存文件数
    """
    global _MAX_CACHE_ENTRIES
    if max_entries < 1:
        raise ValueError("最大缓存条目数必须大于0")
    _MAX_CACHE_ENTRIES = max_entries
    logger.info(f"设置最大缓存条目数为: {max_entries}")


# 执行LRU清理
def _cleanup_cache_directory(dir_path: str):
    """
    清理指定目录的超量缓存文件（LRU策略）
    """
    if not os.path.exists(dir_path):
        return

    # 获取目录下所有缓存文件
    cache_files = [f for f in os.listdir(dir_path) if f.endswith('.csv')]
    if len(cache_files) <= _MAX_CACHE_ENTRIES:
        return

    # 按最后访问时间排序（旧->新）
    file_times = []
    for f in cache_files:
        file_path = os.path.join(dir_path, f)
        file_times.append((f, os.path.getatime(file_path)))

    # 按访问时间排序（最旧在前）
    file_times.sort(key=lambda x: x[1])

    # 计算需要删除的文件数量
    files_to_delete = len(cache_files) - _MAX_CACHE_ENTRIES
    deleted_count = 0

    # 删除最旧的文件
    for file_name, _ in file_times[:files_to_delete]:
        try:
            file_path = os.path.join(dir_path, file_name)
            os.remove(file_path)
            logger.info(f"LRU清理: 删除旧缓存文件 {file_path}")
            deleted_count += 1
        except Exception as e:
            logger.error(f"删除缓存文件失败: {file_path}, 错误: {e}")

    logger.info(f"LRU清理完成: 删除 {deleted_count}/{files_to_delete} 个文件")