# yquoter/config.py
import os
from dotenv import dotenv_values
# 【修改点】导入我们自定义的异常类，用于处理配置相关的错误。
from yquoter.exceptions import ConfigError

_config = None  # 内部缓存

df_cache_path = "" #最新缓存的文件的路径

def get_newest_df_path():
    return df_cache_path

def modify_df_path(path):
    global df_cache_path
    df_cache_path = path

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
    if "LOG_ROOT" not in cfg:
        cfg["LOG_ROOT"] = ".log"
    return cfg



def get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config

def get_tushare_token():
    # 【修改点】重写了此函数以提供更健壮的错误处理。
    token = get_config().get("TUSHARE_TOKEN") # 使用 .get() 安全地获取值，避免KeyError
    if not token:
        # 如果 token 不存在或为空，则抛出我们自定义的、信息更明确的异常。
        # 这比直接抛出 KeyError 对用户更友好。
        raise ConfigError("TUSHARE_TOKEN 未在 .env 文件或系统环境变量中设置！")
    return token

def get_cache_root():
    # 【注释】此函数已是健壮的。
    # 使用 .get() 方法并提供默认值，可以优雅地处理 "CACHE_ROOT" 未设置的情况，
    # 不会抛出异常，因此无需修改。
    return get_config().get("CACHE_ROOT", ".cache")

def get_log_root():
    return get_config().get("LOG_ROOT", ".log")