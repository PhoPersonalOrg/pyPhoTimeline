---
name: Thread-safe Log Widget
overview: Create a thread-safe PyQt6 log widget that displays program logs asynchronously using a custom logging handler that emits Qt signals, preventing main thread blocking from Jupyter notebook output.
todos:
  - id: create_log_widget
    content: Create pypho_timeline/widgets/log_widget.py with QtLogHandler (QObject + logging.Handler) and LogWidget (QWidget with QPlainTextEdit, search, clear, auto-scroll)
    status: completed
  - id: update_logging_util
    content: Add add_qt_log_handler() function to pypho_timeline/utils/logging_util.py to integrate Qt handler with existing logging system
    status: completed
    dependencies:
      - create_log_widget
  - id: update_widgets_init
    content: Export LogWidget and QtLogHandler from pypho_timeline/widgets/__init__.py
    status: completed
    dependencies:
      - create_log_widget
---

# Thread-safe Log Widget Implementation

## Overview

Create a standalone PyQt6 log widget that integrates with the existing logging system to display logs asynchronously without blocking the main thread. The widget will use a custom logging handler that emits Qt signals for thread-safe communication.

## Architecture

The solution consists of three main components:

1. **QtLogHandler** - Custom logging handler that emits Qt signals
2. **LogWidget** - PyQt6 widget for displaying logs with search, clear, and auto-scroll
3. **Integration** - Update `logging_util.py` to support adding the Qt handler

## Implementation Details

### 1. Create `pypho_timeline/widgets/log_widget.py`

**QtLogHandler class:**

- Inherits from `logging.Handler` and `QtCore.QObject`
- Emits `log_record_received` signal with formatted log message
- Thread-safe signal emission using `Qt.QueuedConnection`
- Formats log records using the same formatter as existing handlers

**LogWidget class:**

- Inherits from `QtWidgets.QWidget`
- Uses `QPlainTextEdit` for log display (better performance than QTextEdit for large text)
- Features:
  - Auto-scroll to bottom when new logs arrive (toggleable)
  - Clear button to clear the display
  - Search/filter input with highlighting
  - Color-coding by log level (optional styling)
- Thread-safe: Receives log messages via Qt signals on main thread
- Performance: Limits displayed lines to prevent memory issues (e.g., max 10,000 lines)

### 2. Update `pypho_timeline/utils/logging_util.py`

**Add function: `add_qt_log_handler(logger, log_widget, log_level=logging.DEBUG)`**

- Adds QtLogHandler to the specified logger
- Connects handler signal to widget slot
- Returns the handler instance for later removal if needed
- Prevents duplicate handlers

**Modify `configure_logging()` (optional enhancement):**

- Add optional parameter `log_widget: Optional[LogWidget] = None`
- If provided, automatically add Qt handler

### 3. Update `pypho_timeline/widgets/__init__.py`

- Export `LogWidget` and `QtLogHandler` for easy importing

## Key Design Decisions

1. **Thread Safety**: All log processing happens on the main thread via Qt signals. The handler's `emit()` method is thread-safe and automatically queues signals to the main thread.

2. **Performance**: 

   - Use `QPlainTextEdit` instead of `QTextEdit` for better performance with large logs
   - Limit maximum displayed lines with automatic truncation
   - Use `appendPlainText()` for efficient text addition

3. **Integration**: The widget is standalone and can be added to any window or dock area. Users can optionally integrate it into `SimpleTimelineWidget` if desired.

4. **Log Format**: Uses the same formatter as existing handlers for consistency.

## Files to Create/Modify

1. **NEW**: `pypho_timeline/widgets/log_widget.py` - Main widget and handler implementation
2. **MODIFY**: `pypho_timeline/utils/logging_util.py` - Add `add_qt_log_handler()` function
3. **MODIFY**: `pypho_timeline/widgets/__init__.py` - Export new classes

## Usage Example

```python
from pypho_timeline.widgets import LogWidget
from pypho_timeline.utils.logging_util import configure_logging, add_qt_log_handler
import logging

# Create widget
log_widget = LogWidget()

# Configure logging
logger = configure_logging(log_level=logging.DEBUG)

# Add Qt handler
add_qt_log_handler(logger, log_widget, log_level=logging.DEBUG)

# Use in application
log_widget.show()
# or add to dock area
```

## Testing Considerations

- Test with logs from multiple threads
- Verify auto-scroll behavior
- Test search/filter functionality
- Verify clear button works
- Test with high-frequency log messages
- Verify memory usage with very long logs