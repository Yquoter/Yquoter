# yquoter/config.py
import os
from dotenv import dotenv_values

_config = None  # 内部缓存
df_cache_path = None #最新缓存的文件的路径
def load_config():
    """
    加载配置：
    1. 从 .env 文件读取
    2. 系统环境变量覆盖
    """
    cfg = dotenv_values(".env") or {}
    # 系统环境变量优先级更高
    cfg.update(os.environ)

    if "CACHE_ROOT" not in cfg:
        cfg["CACHE_ROOT"] = ".cache"

    return cfg

def get_newest_df_path():
    return df_cache_path

def modify_df_path(path):
    global df_cache_path
    df_cache_path = path

def get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config

def get_tushare_token():
    return get_config()["TUSHARE_TOKEN"]

def get_cache_root():
    return get_config().get("CACHE_ROOT", ".cache")
