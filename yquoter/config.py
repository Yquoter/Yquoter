# yquoter/configs.py
import os
import sys
import yaml
from typing import Any, Dict, List
from dotenv import dotenv_values
from importlib import resources
from yquoter.logger import get_logger
from yquoter.exceptions import ConfigError, PathNotFoundError

logger = get_logger(__name__)

_config = None

df_cache_path = ""  # Path of the latest cached file

def get_newest_df_path():
    """Return path of the latest cached file"""
    logger.info(f"Retrieving newest cached file path: {df_cache_path}")
    return df_cache_path

def modify_df_path(path):
    """Update path of the latest cached file"""
    global df_cache_path
    df_cache_path = path
    logger.info(f"Updated newest cached file path to: {path}")

def load_config_env():
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
        _config = load_config_env()
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

def _load_yaml_config(resource_name: str) -> Dict[str, Any]:
    """
    Internal utility to load a YAML configuration file from the package resources.
    """
    package_name = 'yquoter.configs'

    try:
        config_path = resources.files(package_name) / resource_name
        config_data = config_path.read_text(encoding='utf-8')

    except FileNotFoundError as e:
        error_msg = f"Core configuration file '{resource_name}' not found within the '{package_name}' package."
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    except ImportError as e:
        logger.error("Cannot access package resource: %s", e)
        raise RuntimeError(f"Failed to access package '{package_name}' resources.") from e

    try:
        config = yaml.safe_load(config_data)

    except yaml.YAMLError as e:
        logger.error("Failed to parse YAML content in %s: %s", resource_name, e)
        raise ConfigError(f"Configuration file '{resource_name}' is malformed.") from e

    if not isinstance(config, dict):
        raise ConfigError(f"Configuration file '{resource_name}' has an invalid root format. Expected a dictionary.")

    return config

def load_mapping_config() -> Dict[str, Any]:
    """
    Loads all field mapping configurations from the 'mapping.yaml' file.
    """
    return _load_yaml_config('mapping.yaml')

def load_standard_config() -> Dict[str, Any]:
    """
    Loads all standard field definitions from the 'standard.yaml' file.
    """
    return _load_yaml_config('standard.yaml')

# Expose the global configuration dictionary right after definition
MAPPING_CONFIG: Dict[str, Any] = load_mapping_config()
STANDARD_CONFIG: Dict[str, Any] = load_standard_config()

# Standard realtime data fields defined by Yquoter (used for filtering/validation)
REALTIME_STANDARD_FIELDS: List[str] = STANDARD_CONFIG.get('YQUOTER_REALTIME_STANDARD_FIELDS', [])

# Standard history data fields defined by Yquoter (used for filtering/validation)
HISTORY_STANDARD_FIELDS_FULL: List[str] = STANDARD_CONFIG.get('YQUOTER_HISTORY_STANDARD_FIELDS_FULL', [])
HISTORY_STANDARD_FIELDS_BASIC: List[str] = STANDARD_CONFIG.get('YQUOTER_HISTORY_STANDARD_FIELDS_BASIC', [])

# Mapping for Tushare's rt_k (realtime) interface
TUSHARE_REALTIME_MAPPING: Dict[str, str] = MAPPING_CONFIG.get('TUSHARE_REALTIME_MAPPING', {})

# Mapping for EastMoney K-line spider
EASTMONEY_KLINE_MAPPING: Dict[str, str] = MAPPING_CONFIG.get('EASTMONEY_KLINE_MAPPING', {})

# Mapping for EastMoney Realtime spider
EASTMONEY_REALTIME_MAPPING: Dict[str, str] = MAPPING_CONFIG.get('EASTMONEY_REALTIME_MAPPING', {})

# Mapping for EastMoney Financials spider
EASYMONEY_FINANCIALS_MAPPING: Dict[str, Any] = MAPPING_CONFIG.get('FINANCIAL_REPORT_MAP', {})