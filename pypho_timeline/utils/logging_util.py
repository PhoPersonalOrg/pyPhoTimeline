"""Shared logging utilities for pypho_timeline components.

This module provides common logging configuration functions to ensure consistent
logging behavior across all pypho_timeline modules.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def configure_logging(log_level=logging.DEBUG, log_file: Optional[Path] = None, 
                     log_to_console: bool = True, log_to_file: bool = True):
    """Configure logging for all pypho_timeline modules to output to both console and file.
    
    This function configures the root 'pypho_timeline' logger, which all submodules
    (rendering, widgets, core, etc.) will inherit from. It can be called multiple times
    safely - it will prevent duplicate handlers.
    
    Args:
        log_level: Logging level (default: logging.DEBUG)
        log_file: Path to log file. If None, uses 'timeline_rendering.log' in current directory
        log_to_console: Whether to log to stdout (default: True)
        log_to_file: Whether to log to file (default: True)
        
    Returns:
        Configured logger instance
    """
    # Configure root pypho_timeline logger - all submodules inherit from this
    logger = logging.getLogger('pypho_timeline')
    
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stdout)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        if log_file is None:
            log_file = Path('timeline_rendering.log')
        else:
            log_file = Path(log_file)
        
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Use RotatingFileHandler to prevent log files from growing too large
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to Python's root logger to avoid duplicate messages
    logger.propagate = False
    
    logger.info(f"Logging configured: level={logging.getLevelName(log_level)}, "
                f"console={log_to_console}, file={log_to_file}, log_file={log_file if log_to_file else 'N/A'}")
    
    return logger


def get_rendering_logger(module_name: str):
    """Get a logger for a rendering module with consistent naming.
    
    Args:
        module_name: The module name (e.g., 'pypho_timeline.rendering.graphics.track_renderer')
        
    Returns:
        Logger instance for the module
    """
    return logging.getLogger(module_name)


__all__ = ['configure_logging', 'get_rendering_logger']

