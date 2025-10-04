# yquoter/logger.py

import logging
import os
import sys
from typing import Optional, Union

from yquoter.config import get_log_root


def setup_logging(level: int = logging.INFO):
    """
    初始化全局日志配置（只需调用一次）
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def get_logger(
        name: Optional[str] = None,
        level: Union[int, str] = logging.INFO,
) -> logging.Logger:
    """
    获取模块专用 logger（推荐使用 __name__）
    """
    logger = logging.getLogger(name)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 设置日志级别
    logger.setLevel(level)

    # 添加控制台处理器
    """
    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)
    """
    # 如果指定了日志文件，添加文件处理器
    if name:
        log_filename = f"{name}.log"
        log_file_path = os.path.join(get_log_root(), log_filename)
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        logger.addHandler(file_handler)
    else:
        raise

    return logger

