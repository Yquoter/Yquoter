# yquoter/configs.py
import os
import sys
import yaml
from importlib import resources
from typing import Dict, Any, List
from dotenv import dotenv_values
from yquoter.logger import get_logger
from yquoter.exceptions import ConfigError, PathNotFoundError

logger = get_logger(__name__)

_config = None

df_cache_path = ""  # Path of the latest cached file

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


def load_mapping_config() -> Dict[str, Any]:
    """
    Loads all field mapping configurations from the 'mapping.yaml' file.

    Uses importlib.resources to reliably locate and read the resource file
    after the package has been installed (zip-safe).

    Raises:
        RuntimeError: If the 'mapping.yaml' file cannot be found or read.
        ValueError: If the YAML file contains invalid format.
        yaml.YAMLError: If the YAML content is malformed.

    Returns:
        Dict[str, Any]: A dictionary containing all mapping configurations.
    """

    # The mapping.yaml is expected to be placed in the same directory as the package's
    package_name = 'yquoter.configs'
    resource_name = 'mapping.yaml'

    try:
        # Use importlib.resources.files to locate the resource relative to the package
        config_path = resources.files(package_name) / resource_name

        config_data = config_path.read_text(encoding='utf-8')

    except FileNotFoundError as e:
        # This occurs if the file is missing from the installed package or source tree
        error_msg = f"Core configuration file '{resource_name}' not found within the '{package_name}' package."
        logger.error("Core configuration file 'mapping.yaml' not found: %s", e)
        raise RuntimeError(error_msg) from e

    except ImportError as e:
        # This occurs if the package name itself is incorrect or cannot be imported
        logger.error("Cannot access package resource: %s", e)
        raise RuntimeError(f"Failed to access package '{package_name}' resources.") from e

    # Safely load the YAML content
    try:
        config = yaml.safe_load(config_data)

    except yaml.YAMLError as e:
        logger.error("Failed to parse YAML content in %s: %s", resource_name, e)
        raise ConfigError(f"Mapping configuration file is malformed.") from e

    if not isinstance(config, dict):
        raise ConfigError(f"Mapping configuration file has an invalid root format. Expected a dictionary.")

    return config


# Expose the global configuration dictionary right after definition
MAPPING_CONFIG: Dict[str, Any] = load_mapping_config()

# Standard fields defined by Yquoter (used for filtering/validation)
STANDARD_FIELDS: List[str] = MAPPING_CONFIG.get('YQUOTER_STANDARD_FIELDS', [])

# Mapping for Tushare's rt_k (realtime) interface
TUSHARE_REALTIME_MAPPING: Dict[str, str] = MAPPING_CONFIG.get('TUSHARE_REALTIME_MAPPING', {})

# Mapping for EastMoney K-line spider
EASTMONEY_KLINE_MAPPING: Dict[str, str] = MAPPING_CONFIG.get('EASTMONEY_KLINE_MAPPING', {})