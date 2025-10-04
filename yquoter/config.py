# yquoter/config.py
import os
from dotenv import dotenv_values
from yquoter.exceptions import ConfigError

_config = None

df_cache_path = "" # Path of the latest cached file

def get_newest_df_path():
    """Return path of the latest cached file"""
    return df_cache_path

def modify_df_path(path):
    """Update path of the latest cached file"""
    global df_cache_path
    df_cache_path = path

def load_config():
    """
    Load configuration:
    1. Read from .env file
    2. Override with system environment variables
    """
    cfg = dotenv_values(".env") or {}
    # System environment variables take higher priority
    cfg.update(os.environ)
    if "CACHE_ROOT" not in cfg:
        cfg["CACHE_ROOT"] = ".cache"
    if "LOG_ROOT" not in cfg:
        cfg["LOG_ROOT"] = ".log"
    return cfg



def get_config():
    """Get configuration (load if not initialized)"""
    global _config
    if _config is None:
        _config = load_config()
    return _config

def get_tushare_token():
    """Get tushare token with error handling"""
    token = get_config().get("TUSHARE_TOKEN")
    if not token:
        raise ConfigError("TUSHARE_TOKEN not set in .env file or system environment variables!")
    return token

def get_cache_root():
    """Get cache root directory (with default value)"""
    return get_config().get("CACHE_ROOT", ".cache")

def get_log_root():
    """Get log root directory (with default value)"""
    return get_config().get("LOG_ROOT", ".log")