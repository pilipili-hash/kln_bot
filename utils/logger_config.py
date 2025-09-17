"""
日志配置模块 - 统一配置应用日志
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    设置应用日志配置
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为None则使用默认路径
        max_file_size: 日志文件最大大小（字节）
        backup_count: 保留的备份文件数量
        console_output: 是否输出到控制台
    """
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 如果没有指定日志文件，使用默认文件名
    if log_file is None:
        today = datetime.now().strftime("%Y_%m_%d")
        log_file = log_dir / f"bot_{today}.log"
    else:
        log_file = Path(log_file)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 添加文件处理器（带轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # 控制台只显示INFO及以上级别
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    
    # 设置一些第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    
    logging.info("日志系统初始化完成")

def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)
