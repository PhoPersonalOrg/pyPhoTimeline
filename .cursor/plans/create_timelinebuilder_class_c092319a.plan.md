---
name: Create TimelineBuilder class
overview: Create a new `TimelineBuilder` class in `timeline_builder.py` that encapsulates building and updating timeline widgets from various input sources. Refactor the existing `main_all_modalities_from_xdf_file_example` function to use this new class.
todos:
  - id: create_timeline_builder_file
    content: Create new file pypho_timeline/timeline_builder.py with TimelineBuilder class structure and imports
    status: completed
  - id: implement_build_from_xdf
    content: Implement build_from_xdf_file() method that refactors the logic from main_all_modalities_from_xdf_file_example
    status: completed
    dependencies:
      - create_timeline_builder_file
  - id: implement_helper_methods
    content: "Implement helper methods: _process_xdf_streams(), _add_tracks_to_timeline(), and other internal helpers"
    status: completed
    dependencies:
      - create_timeline_builder_file
  - id: implement_build_from_streams
    content: Implement build_from_streams() method for building from pre-loaded streams
    status: completed
    dependencies:
      - implement_helper_methods
  - id: implement_build_from_datasources
    content: Implement build_from_datasources() method for building from existing datasources
    status: completed
    dependencies:
      - implement_helper_methods
  - id: implement_update_timeline
    content: Implement update_timeline() method for adding tracks to existing timeline widgets
    status: completed
    dependencies:
      - implement_helper_methods
  - id: refactor_main_function
    content: Refactor main_all_modalities_from_xdf_file_example() in __main__.py to use TimelineBuilder
    status: completed
    dependencies:
      - implement_build_from_xdf
  - id: update_package_init
    content: Optionally update pypho_timeline/__init__.py to export TimelineBuilder if it should be part of public API
    status: completed
    dependencies:
      - create_timeline_builder_file
---

# Create TimelineBuilder Class

## Overview

Create a new `TimelineBuilder` class that provides a unified interface for building and updating `SimpleTimelineWidget` instances from various input sources. The class will initially support XDF files and be designed to easily extend to other input sources.

## Files to Create/Modify

### 1. Create new file: `pypho_timeline/timeline_builder.py`

Create a new `TimelineBuilder` class with the following structure:**Class Design:**

- `TimelineBuilder` class with methods for building/updating timeline widgets
- Support for multiple input sources (XDF files initially, extensible design)
- Methods to build new widgets or update existing ones
- Configurable logging and widget properties

**Key Methods:**

- `build_from_xdf_file(xdf_file_path: Path, ...)` - Build timeline from XDF file (refactors current function)
- `build_from_streams(streams: List, ...)` - Build timeline from pre-loaded streams
- `build_from_datasources(datasources: List[TrackDatasource], ...)` - Build timeline from existing datasources
- `update_timeline(timeline: SimpleTimelineWidget, ...)` - Add tracks to existing timeline widget
- `_process_xdf_streams(streams)` - Internal helper to process XDF streams
- `_add_tracks_to_timeline(timeline, datasources)` - Internal helper to add tracks

**Dependencies:**

- Import `SimpleTimelineWidget`, `perform_process_all_streams` from `pypho_timeline.widgets`
- Import `SynchronizedPlotMode` from `pypho_timeline.core.synchronized_plot_mode`
- Import `configure_logging` from `pypho_timeline.utils.logging_util`
- Import `pyxdf`, `numpy`, `pandas`, `Path` as needed

### 2. Update `pypho_timeline/__main__.py`

**Changes:**

- Refactor `main_all_modalities_from_xdf_file_example()` function (lines 118-255) to use `TimelineBuilder`
- Replace the implementation with a call to `TimelineBuilder().build_from_xdf_file(xdf_file_path)`
- Keep the function signature and return value the same for backward compatibility
- Import `TimelineBuilder` from `pypho_timeline.timeline_builder`

**Refactored function should:**

```python
def main_all_modalities_from_xdf_file_example(xdf_file_path: Path):
    """Main function demonstrating pyPhoTimeline usage with all EEG modalities from an XDF file."""
    builder = TimelineBuilder()
    return builder.build_from_xdf_file(xdf_file_path)
```



### 3. Update `pypho_timeline/__init__.py` (optional)

Consider exporting `TimelineBuilder` from the main package `__init__.py` if it should be part of the public API.

## Implementation Details

**TimelineBuilder Class Structure:**

```python
class TimelineBuilder:
    def __init__(self, log_level=logging.DEBUG, log_file=None, log_to_console=True, log_to_file=True):
        # Store logging configuration
        
    def build_from_xdf_file(self, xdf_file_path: Path, window_duration=None, ...) -> SimpleTimelineWidget:
        # Load XDF, process streams, create timeline, add tracks
        
    def build_from_streams(self, streams: List, ...) -> SimpleTimelineWidget:
        # Process streams, create timeline, add tracks
        
    def build_from_datasources(self, datasources: List[TrackDatasource], ...) -> SimpleTimelineWidget:
        # Create timeline from existing datasources
        
    def update_timeline(self, timeline: SimpleTimelineWidget, datasources: List[TrackDatasource]) -> SimpleTimelineWidget:
        # Add tracks to existing timeline
        
    def _process_xdf_streams(self, streams) -> Tuple[Dict, Dict]:
        # Internal: process streams using perform_process_all_streams
        
    def _add_tracks_to_timeline(self, timeline: SimpleTimelineWidget, datasources: List[TrackDatasource]) -> None:
        # Internal: add tracks with proper configuration
```

**Key Features:**

- Extract all the logic from `main_all_modalities_from_xdf_file_example` into the builder
- Make logging configuration optional and configurable
- Support both creating new widgets and updating existing ones
- Calculate time ranges automatically from datasources
- Handle window duration calculation (current logic: `max(total_end_time - total_start_time, 10.0)`)
- Preserve all existing functionality (dock configuration, plot setup, track rendering)

## Design Considerations

1. **Extensibility**: Design methods to easily add new input sources (e.g., CSV files, database connections, etc.)
2. **Backward Compatibility**: Keep `main_all_modalities_from_xdf_file_example` function signature unchanged
3. **Separation of Concerns**: Builder handles widget creation/configuration, while widget handles rendering/interaction