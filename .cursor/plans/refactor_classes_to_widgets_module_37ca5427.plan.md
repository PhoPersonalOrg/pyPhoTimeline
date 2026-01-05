---
name: Refactor classes to widgets module
overview: Move SimpleTimelineWidget class, modality dictionaries, and perform_process_all_streams function from __main__.py to a new file in the widgets directory, and update all imports accordingly.
todos:
  - id: create_widget_file
    content: Create new file pypho_timeline/widgets/simple_timeline_widget.py with SimpleTimelineWidget class, modality dictionaries, and perform_process_all_streams function
    status: completed
  - id: update_widgets_init
    content: Update pypho_timeline/widgets/__init__.py to export the new classes and functions
    status: completed
    dependencies:
      - create_widget_file
  - id: update_main_file
    content: Remove moved code from __main__.py and add import from widgets module
    status: completed
    dependencies:
      - create_widget_file
  - id: update_notebook_imports
    content: Update testing_notebook.ipynb to import from widgets instead of __main__
    status: completed
    dependencies:
      - update_widgets_init
---

# Refactor Timeline Classes to Widgets Module

## Overview

Refactor the `SimpleTimelineWidget` class, modality configuration dictionaries, and `perform_process_all_streams` function from `pypho_timeline/__main__.py` (lines 46-454) to a new file in the `widgets` directory.

## Files to Modify

### 1. Create new file: `pypho_timeline/widgets/simple_timeline_widget.py`

- Move `SimpleTimelineWidget` class (lines 47-368 from `__main__.py`)
    - Includes nested `SimpleTimeWindow` class (lines 84-95)
    - Includes `interval_rendering_plots` property (lines 53-60)
    - Includes `__init__`, `setupUI`, `add_example_tracks`, and `simulate_window_scroll` methods
- Move `modality_channels_dict` dictionary (lines 371-374)
- Move `modality_sfreq_dict` dictionary (lines 376-378)
- Move `perform_process_all_streams` function (lines 381-451)
- Include all necessary imports at the top of the new file

### 2. Update `pypho_timeline/widgets/__init__.py`

- Add exports for:
    - `SimpleTimelineWidget`
    - `modality_channels_dict`
    - `modality_sfreq_dict`
    - `perform_process_all_streams`
- Update `__all__` list accordingly

### 3. Update `pypho_timeline/__main__.py`

- Remove lines 46-454 (the classes/functions being moved)
- Add import statement to import from widgets:
     ```python
                    from pypho_timeline.widgets import SimpleTimelineWidget, perform_process_all_streams, modality_channels_dict, modality_sfreq_dict
     ```




- Ensure `main()` and `main_all_modalities_from_xdf_file_example()` functions still work (they reference `SimpleTimelineWidget` and `perform_process_all_streams`)

### 4. Update `testing_notebook.ipynb`

- Change import from:
     ```python
                    from pypho_timeline.__main__ import ..., SimpleTimelineWidget, ..., perform_process_all_streams, ...
     ```




- To:
     ```python
                    from pypho_timeline.widgets import SimpleTimelineWidget, perform_process_all_streams
                    from pypho_timeline.__main__ import ...  # other imports
     ```




## Implementation Details

- All imports needed by the moved code must be included in the new file
- The nested `SimpleTimeWindow` class stays inside `SimpleTimelineWidget.__init__` as it's only used internally
- Maintain all existing functionality - this is purely a structural refactoring
- Follow the project's function signature formatting rules (single-line signatures when possible)

## Dependencies to Include in New File

Based on the code analysis, the new file will need these imports:

- `numpy`, `pandas`
- `QtWidgets`, `QtCore` from `qtpy`
- `pg` (pyqtgraph)
- All the timeline-related imports (SynchronizedPlotMode, NestedDockAreaWidget, etc.)
- Track datasource imports