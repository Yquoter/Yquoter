# yquoter/logger.py

import logging
from typing import Optional

def setup_logging(level: int = logging.INFO):
    """
    初始化全局日志配置（只需调用一次）
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取模块专用 logger（推荐使用 __name__）
    """
    return logging.getLogger(name)
