import os
import pandas as pd
from typing import Optional
from yquoter.logger import get_logger
from yquoter.config import get_cache_root, modify_df_path

# ---------- 日志配置 ----------
logger = get_logger(__name__)

# 全局缓存管理变量
_cache_file_list = []  # 存储缓存文件路径的列表
_MAX_CACHE_ENTRIES = 100  # 默认最大缓存条目数


def init_cache_manager():
    """
    初始化缓存管理器，扫描缓存目录并加载文件列表
    """
    global _cache_file_list
    cache_root = get_cache_root()

    # 清空现有列表
    _cache_file_list = []

    # 遍历缓存目录下的所有CSV文件
    for root, dirs, files in os.walk(cache_root):
        for file in files:
            if file.endswith('.csv'):
                path = os.path.join(root, file)
                if os.path.exists(path):  # 确保文件存在
                    # 获取文件修改时间作为缓存时间
                    mtime = os.path.getmtime(path)
                    _cache_file_list.append((mtime, path))

    # 按修改时间排序（旧->新）
    _cache_file_list.sort(key=lambda x: x[0])
    logger.info(f"初始化缓存管理器，找到 {len(_cache_file_list)} 个缓存文件")

    # 执行初始清理（如果文件数量超过限制）
    _cleanup_old_cache()


def _add_cache_file(path: str):
    """
    添加新的缓存文件到管理列表，并执行清理（内部函数）
    """
    global _cache_file_list

    if not os.path.exists(path):
        logger.warning(f"尝试添加不存在的缓存文件: {path}")
        return

    mtime = os.path.getmtime(path)

    # 检查是否已存在，如果存在则更新
    for i, (existing_mtime, existing_path) in enumerate(_cache_file_list):
        if existing_path == path:
            _cache_file_list[i] = (mtime, path)
            break
    else:
        # 如果不存在则添加
        _cache_file_list.append((mtime, path))

    # 按修改时间排序
    _cache_file_list.sort(key=lambda x: x[0])

    # 清理旧缓存
    _cleanup_old_cache()


def _cleanup_old_cache():
    """
    清理超过数量限制的旧缓存文件
    """
    global _cache_file_list

    # 计算需要删除的文件数量
    if len(_cache_file_list) <= _MAX_CACHE_ENTRIES:
        return

    files_to_delete = len(_cache_file_list) - _MAX_CACHE_ENTRIES
    deleted_count = 0

    # 删除最旧的文件
    for _ in range(files_to_delete):
        if not _cache_file_list:
            break

        _, oldest_path = _cache_file_list.pop(0)
        try:
            if os.path.exists(oldest_path):
                os.remove(oldest_path)
                logger.info(f"缓存清理: 删除旧文件 {oldest_path}")
                deleted_count += 1
        except Exception as e:
            logger.error(f"删除缓存文件失败: {oldest_path}, 错误: {e}")

    if deleted_count > 0:
        logger.info(f"缓存清理完成: 删除 {deleted_count} 个旧文件")


def set_max_cache_entries(max_entries: int):
    """
    设置最大缓存条目数并执行清理
    """
    global _MAX_CACHE_ENTRIES
    if max_entries < 1:
        raise ValueError("最大缓存条目数必须大于0")
    _MAX_CACHE_ENTRIES = max_entries
    logger.info(f"设置最大缓存条目数为: {max_entries}")

    # 立即执行清理
    _cleanup_old_cache()


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

        # 添加到缓存管理系统
        _add_cache_file(path)

    except Exception as e:
        logger.error(f"保存缓存文件失败: {path}，异常: {e}")
        raise