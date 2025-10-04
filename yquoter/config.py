# yquoter/config.py
import os
from dotenv import dotenv_values
from yquoter.exceptions import ConfigError
from yquoter.logger import get_logger
logger = get_logger(__name__)
_config = None

df_cache_path = "" # Path of the latest cached file

def get_newest_df_path():
    """Return path of the latest cached file"""
    logger.info(f"Retrieving newest cached file path: {df_cache_path}")
    return df_cache_path

def modify_df_path(path):
    """Update path of the latest cached file"""
    global df_cache_path
    df_cache_path = path
    logger.info(f"Updated newest cached file path to: {path}")

def load_config():
    """
    Load configuration:
    1. Read from .env file
    2. Override with system environment variables
    """
    logger.info("Starting to load configuration")
    cfg = dotenv_values(".env") or {}
    # System environment variables take higher priority
    cfg.update(os.environ)
    if "CACHE_ROOT" not in cfg:
        cfg["CACHE_ROOT"] = ".cache"
    if "LOG_ROOT" not in cfg:
        cfg["LOG_ROOT"] = ".log"
    logger.info("Configuration loaded successfully")
    return cfg



def get_config():
    """Get configuration (load if not initialized)"""
    global _config
    if _config is None:
        logger.info("Configuration not initialized, loading now")
        _config = load_config()
    logger.info("Configuration retrieved successfully")
    return _config

def get_tushare_token():
    """Get tushare token with error handling"""
    logger.info("Attempting to get Tushare token")
    token = get_config().get("TUSHARE_TOKEN")
    if not token:
        logger.error("TUSHARE_TOKEN not set in .env file or system environment variables!")
        raise ConfigError("TUSHARE_TOKEN not set in .env file or system environment variables!")
    logger.info("Tushare token retrieved successfully")
    return token

def get_cache_root():
    """Get cache root directory (with default value)"""
    cache_root = get_config().get("CACHE_ROOT", ".cache")
    logger.info(f"Cache root directory retrieved: {cache_root}")
    return cache_root

def get_log_root():
    """Get log root directory (with default value)"""
    log_root = get_config().get("LOG_ROOT", ".log")
    logger.info(f"Log root directory retrieved: {log_root}")
    return log_root

