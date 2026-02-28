"""Shared logging utilities for pypho_timeline components.

This module provides common logging configuration functions to ensure consistent
logging behavior across all pypho_timeline modules.

Usage:
    from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log

    logger = get_rendering_logger(__name__)



"""
from typing import Any, Optional, Dict, Tuple
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import pandas as pd


def configure_logging(log_level=logging.DEBUG, log_file: Optional[Path] = None, log_to_console: bool = True, log_to_file: bool = True):
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
    
    # Create formatter (include threadName for async/debugging)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
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
            log_file = Path('EXTERNAL/LOGGING').resolve().joinpath('timeline_rendering.log')
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


def add_qt_log_handler(logger: logging.Logger, log_widget, log_level=logging.DEBUG):
    """Add a Qt log handler to a logger for thread-safe log display in a widget.
    
    This function creates a QtLogHandler and connects it to the provided log widget.
    The handler will emit Qt signals when log records are received, ensuring
    thread-safe display of logs from any thread.
    
    Args:
        logger: Logger instance to add the handler to
        log_widget: LogWidget instance to receive log messages
        log_level: Logging level for the handler (default: logging.DEBUG)
        
    Returns:
        QtLogHandler instance that was added
        
    Example:
        from pypho_timeline.widgets import LogWidget
        from pypho_timeline.utils.logging_util import configure_logging, add_qt_log_handler
        import logging
        
        log_widget = LogWidget()
        logger = configure_logging(log_level=logging.DEBUG)
        handler = add_qt_log_handler(logger, log_widget, log_level=logging.DEBUG)
    """
    # Import here to avoid circular dependencies
    from qtpy import QtCore
    from pypho_timeline.widgets.log_widget import QtLogHandler
    
    # Check if handler already exists
    for existing_handler in logger.handlers:
        if isinstance(existing_handler, QtLogHandler):
            # Handler already exists, just update the connection if needed
            # Disconnect old connections and reconnect to new widget
            existing_handler.log_record_received.disconnect()
            existing_handler.log_record_received.connect(log_widget.append_log)
            return existing_handler
    
    # Create new handler
    handler = QtLogHandler()
    handler.setLevel(log_level)
    
    # Use the same formatter as other handlers if available
    if logger.handlers:
        handler.setFormatter(logger.handlers[0].formatter)
    else:
        # Use default formatter
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    # Connect handler signal to widget slot
    # Use QueuedConnection to ensure thread-safe delivery (Qt will use this automatically if needed)
    handler.log_record_received.connect(log_widget.append_log, QtCore.Qt.ConnectionType.QueuedConnection)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return handler





def _format_time_value_for_log(value: Any) -> str:
    """Format a single time value (t_start) for logging. Never raises."""
    if value is None:
        return "?"
    try:
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.isoformat() if hasattr(value, 'isoformat') else str(value)
        try:
            ts = pd.Timestamp(value)
            return ts.isoformat()
        except (ValueError, TypeError, AttributeError):
            pass
        return f"{float(value)}"
    except Exception:
        return repr(value)


def _format_duration_value_for_log(value: Any) -> str:
    """Format a single duration value (t_duration) for logging. Never raises."""
    if value is None:
        return "?"
    try:
        if isinstance(value, (timedelta, pd.Timedelta)):
            return f"{value.total_seconds()}s"
        try:
            td = pd.Timedelta(value)
            return f"{td.total_seconds()}s"
        except (ValueError, TypeError, AttributeError):
            pass
        return f"{float(value)}"
    except Exception:
        return repr(value)


def _format_interval_for_log(interval: pd.Series) -> str:
    """Format t_start and t_duration for logging; supports float, datetime, timedelta, None. Never raises.

    from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log

    """
    try:
        t_start = interval.get('t_start', None)
        t_duration = interval.get('t_duration', None)
        t_start_str = _format_time_value_for_log(t_start)
        t_duration_str = _format_duration_value_for_log(t_duration)
        return f"t_start={t_start_str}, t_duration={t_duration_str}"
    except Exception as e:
        return f"<format error: {e}>"

__all__ = ['configure_logging', 'get_rendering_logger', 'add_qt_log_handler']

