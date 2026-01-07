---
name: Remove backward compatibility logging aliases
overview: Remove the backward compatibility aliases `configure_rendering_logging` and `configure_all_logging` from the logging utility module and update exports, since the codebase already uses the correct `configure_logging` function.
todos: []
---

# Remove Backward Compatibility Logging Aliases

## Overview

Remove the backward compatibility aliases `configure_rendering_logging` and `configure_all_logging` from the logging utility module and clean up exports, since the codebase is already using the correct `configure_logging` function.

## Files to Modify

### 1. `pypho_timeline/utils/logging_util.py`

- Remove lines 80-85 (the backward compatibility alias assignments)
- Update `__all__` on line 100 to remove `'configure_rendering_logging'` and `'configure_all_logging'`

### 2. `pypho_timeline/utils/__init__.py`

- Remove `configure_rendering_logging` and `configure_all_logging` from the import statement on line 7
- Remove them from the `__all__` list (lines 17-18)

## Changes

**Before:**

```python
# Backward compatibility alias
configure_rendering_logging = configure_logging

# Convenience alias for backward compatibility
configure_all_logging = configure_logging
```