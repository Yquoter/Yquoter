# yquoter/logger.py

import logging
import os
import sys
from typing import Optional, Union

from yquoter.config import get_log_root


def setup_logging(level: int = logging.INFO):
    """
    Initialize global logging configuration (call only once)

        Args:
            level: Logging severity level (default: logging.INFO).

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
    Get a module-specific logger (recommended to use __name__ as 'name' parameter)

        Args:
            name: Unique name for the logger (typically the module name __name__).
                  If provided, logs will be written to a dedicated file; if None, raises error.
            level: Logging severity level (can be int constant like logging.DEBUG or string like "INFO", default: logging.INFO)

        Returns:
            Configured logging.Logger instance

        Raises:
            Exception: If 'name' is None (logger name is required for file logging)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Set logger severity level
    logger.setLevel(level)

    # Console handler (commented out in original code, retained for reference)
    """
    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)
    """

    # Add file handler if logger name is provided
    if name:
        log_filename = f"{name}.log"
        log_file_path = os.path.join(get_log_root(), log_filename)
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Create file handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        logger.addHandler(file_handler)
    else:
        raise

    return logger

