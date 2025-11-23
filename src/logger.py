# src/logger.py

"""Logging configuration cho toàn bộ hệ thống."""

import logging
import os
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console: bool = True
) -> logging.Logger:
    """
    Tạo logger với format chuẩn.
    
    Args:
        name: Tên logger (thường là __name__)
        log_file: Đường dẫn file log (None = không log ra file)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Có log ra console không
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Tránh duplicate handlers nếu gọi nhiều lần
    if logger.handlers:
        return logger
    
    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Default loggers cho các module
def get_logger(module_name: str) -> logging.Logger:
    """
    Lấy logger cho module với cấu hình mặc định.
    
    Args:
        module_name: Tên module (thường là __name__)
        
    Returns:
        Logger instance
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, 'logs')
    
    # Tạo tên file log theo ngày
    date_str = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f'app_{date_str}.log')
    
    return setup_logger(
        name=module_name,
        log_file=log_file,
        level=logging.INFO,
        console=True
    )

