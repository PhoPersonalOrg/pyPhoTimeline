"""Thread-safe log widget for displaying program logs in PyQt6.

This module provides a custom logging handler that emits Qt signals for thread-safe
log display, and a widget for viewing logs with search, clear, and auto-scroll features.
"""
import logging
from typing import Optional
from qtpy import QtCore, QtGui, QtWidgets
from pypho_timeline.utils.logging_util import get_rendering_logger

logger = get_rendering_logger(__name__)


class QtLogHandler(logging.Handler, QtCore.QObject):
    """Custom logging handler that emits Qt signals for thread-safe log display.
    
    This handler can be used from any thread. When a log record is emitted,
    it formats the record and emits a Qt signal that will be processed on the
    main thread, ensuring thread-safe log display.
    
    Usage:
        handler = QtLogHandler()
        handler.log_record_received.connect(log_widget.append_log)
        logger.addHandler(handler)
    """
    
    # Signal emitted when a log record is received
    # Parameters: (formatted_message: str, log_level: int, log_level_name: str)
    log_record_received = QtCore.Signal(str, int, str)
    
    def __init__(self, parent=None):
        """Initialize the Qt log handler.
        
        Args:
            parent: Parent QObject
        """
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self, parent)
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record as a Qt signal.
        
        This method is called by the logging system when a log record is emitted.
        It formats the record and emits a Qt signal that will be processed on
        the main thread.
        
        Args:
            record: LogRecord from the logging system
        """
        try:
            formatted_message = self.format(record)
            log_level = record.levelno
            log_level_name = record.levelname
            # Emit signal - Qt automatically handles thread-safe queuing
            self.log_record_received.emit(formatted_message, log_level, log_level_name)
        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)


class LogWidget(QtWidgets.QWidget):
    """Widget for displaying program logs with search, clear, and auto-scroll features.
    
    This widget receives log messages via Qt signals, ensuring thread-safe display
    of logs from any thread. It provides:
    - Auto-scroll to latest entries (toggleable)
    - Clear button to clear the display
    - Search/filter input with text highlighting
    - Performance optimization for large logs (max line limit)
    
    Usage:
        log_widget = LogWidget()
        handler = QtLogHandler()
        handler.log_record_received.connect(log_widget.append_log)
        logger.addHandler(handler)
        log_widget.show()
    """
    
    def __init__(self, max_lines: int = 10000, parent=None):
        """Initialize the log widget.
        
        Args:
            max_lines: Maximum number of lines to keep in display (default: 10000)
            parent: Parent widget
        """
        super().__init__(parent)
        self.max_lines = max_lines
        self._auto_scroll_enabled = True
        self._mark_count = 0
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Control panel
        control_layout = QtWidgets.QHBoxLayout()
        
        # Search input
        search_label = QtWidgets.QLabel("Search:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Filter logs...")
        self.search_input.textChanged.connect(self._on_search_changed)
        
        # Auto-scroll checkbox
        self.auto_scroll_checkbox = QtWidgets.QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.stateChanged.connect(self._on_auto_scroll_changed)
        
        # Mark button
        mark_button = QtWidgets.QPushButton("Mark")
        mark_button.clicked.connect(self._on_mark_clicked)
        # Clear button
        clear_button = QtWidgets.QPushButton("Clear")
        clear_button.clicked.connect(self._on_clear_clicked)
        
        control_layout.addWidget(search_label)
        control_layout.addWidget(self.search_input)
        control_layout.addStretch()
        control_layout.addWidget(self.auto_scroll_checkbox)
        control_layout.addWidget(mark_button)
        control_layout.addWidget(clear_button)
        
        layout.addLayout(control_layout)
        
        # Log display
        self.log_display = QtWidgets.QPlainTextEdit()
        self.log_display.setReadOnly(True)
        # Use monospace font for better log readability
        font = QtGui.QFont("Consolas", 6)
        if not font.exactMatch():
            font = QtGui.QFont("Courier", 6)
        self.log_display.setFont(font)
        self.log_display.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        
        # Store original text for filtering
        self._all_logs = []
        self._current_filter = ""
        
        layout.addWidget(self.log_display)
    
    def append_log(self, formatted_message: str, log_level: int, log_level_name: str):
        """Append a log message to the display.
        
        This method is called via Qt signal connection from QtLogHandler.
        It is thread-safe because it runs on the main thread.
        
        Args:
            formatted_message: Formatted log message
            log_level: Numeric log level (logging.DEBUG, logging.INFO, etc.)
            log_level_name: String log level name ("DEBUG", "INFO", etc.)
        """
        # Add to stored logs
        log_entry = {
            'message': formatted_message,
            'level': log_level,
            'level_name': log_level_name
        }
        self._all_logs.append(log_entry)
        
        # Apply current filter
        if self._current_filter:
            if self._current_filter.lower() not in formatted_message.lower():
                return  # Don't display if it doesn't match filter
        
        # Append to display
        self.log_display.appendPlainText(formatted_message)
        
        # Limit displayed lines
        if self.log_display.document().blockCount() > self.max_lines:
            cursor = self.log_display.textCursor()
            cursor.movePosition(QtCore.QTextCursor.MoveOperation.Start)
            cursor.movePosition(QtCore.QTextCursor.MoveOperation.Down, QtCore.QTextCursor.MoveMode.KeepAnchor, 
                              self.log_display.document().blockCount() - self.max_lines)
            cursor.removeSelectedText()
        
        # Auto-scroll to bottom if enabled
        if self._auto_scroll_enabled:
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _on_search_changed(self, text: str):
        """Handle search text change.
        
        Args:
            text: Search text
        """
        self._current_filter = text
        self._refresh_display()
    
    def _on_auto_scroll_changed(self, state: int):
        """Handle auto-scroll checkbox change.
        
        Args:
            state: Checkbox state
        """
        self._auto_scroll_enabled = (state == QtCore.Qt.CheckState.Checked)
    
    def _on_mark_clicked(self):
        """Insert a long marker line into the log for easy visual reference."""
        self._mark_count += 1
        line = "_" * 90 + f" MARK {self._mark_count} " + "_" * 90 + "\n"
        self.append_log(line.rstrip(), logging.INFO, "INFO")


    def _on_clear_clicked(self):
        """Handle clear button click."""
        self.log_display.clear()
        self._all_logs = []
        self._current_filter = ""
        self.search_input.clear()
        self._mark_count = 0
    
    def _refresh_display(self):
        """Refresh the display based on current filter."""
        self.log_display.clear()
        
        filter_lower = self._current_filter.lower() if self._current_filter else ""
        
        for log_entry in self._all_logs:
            if not filter_lower or filter_lower in log_entry['message'].lower():
                self.log_display.appendPlainText(log_entry['message'])
        
        # Auto-scroll to bottom if enabled
        if self._auto_scroll_enabled:
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())


__all__ = ['QtLogHandler', 'LogWidget']
