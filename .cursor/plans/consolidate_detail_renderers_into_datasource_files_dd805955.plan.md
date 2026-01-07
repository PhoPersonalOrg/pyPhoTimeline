---
name: Consolidate detail renderers into datasource files
overview: Move MotionPlotDetailRenderer, PositionPlotDetailRenderer, and VideoThumbnailDetailRenderer from detail_renderers/ into their corresponding datasource files (motion.py, position.py, video.py) to match the pattern established in eeg.py, then update all imports and delete the old renderer files.
todos:
  - id: consolidate_motion
    content: Move MotionPlotDetailRenderer class from motion_plot_renderer.py into motion.py, remove old import, update __all__
    status: pending
  - id: consolidate_position
    content: Move PositionPlotDetailRenderer class from position_plot_renderer.py into position.py, remove old import, update __all__
    status: pending
  - id: consolidate_video
    content: Move VideoThumbnailDetailRenderer class from video_thumbnail_renderer.py into video.py, remove old import, update __all__
    status: pending
  - id: update_specific_init
    content: Update datasources/specific/__init__.py to export the three renderer classes
    status: pending
    dependencies:
      - consolidate_motion
      - consolidate_position
      - consolidate_video
  - id: update_detail_renderers_init
    content: Update detail_renderers/__init__.py to import renderers from datasources.specific and re-export them
    status: pending
    dependencies:
      - consolidate_motion
      - consolidate_position
      - consolidate_video
  - id: update_main_imports
    content: Update __main__.py imports (optional - can keep using detail_renderers import)
    status: pending
    dependencies:
      - update_detail_renderers_init
  - id: delete_old_files
    content: Delete motion_plot_renderer.py, position_plot_renderer.py, and video_thumbnail_renderer.py
    status: pending
    dependencies:
      - update_detail_renderers_init
---

# Consolidate Detail Renderers into Datasource Files

## Overview

Consolidate modality-specific detail renderers into their corresponding datasource files to match the pattern established in `eeg.py`. This improves code organization by keeping related classes together and eliminates the split between `datasources/specific/` and `detail_renderers/` for modality-specific code.

## Files to Consolidate

### 1. Motion

- **Source**: `rendering/detail_renderers/motion_plot_renderer.py` (221 lines)
- **Destination**: `rendering/datasources/specific/motion.py`
- **Class**: `MotionPlotDetailRenderer` → Move into `motion.py` before `MotionTrackDatasource`

### 2. Position

- **Source**: `rendering/detail_renderers/position_plot_renderer.py` (128 lines)
- **Destination**: `rendering/datasources/specific/position.py`
- **Class**: `PositionPlotDetailRenderer` → Move into `position.py` before `PositionTrackDatasource`

### 3. Video

- **Source**: `rendering/detail_renderers/video_thumbnail_renderer.py` (190 lines)
- **Destination**: `rendering/datasources/specific/video.py`
- **Class**: `VideoThumbnailDetailRenderer` → Move into `video.py` before `VideoTrackDatasource`

## Implementation Steps

### Step 1: Update `motion.py`

- Remove import: `from pypho_timeline.rendering.detail_renderers.motion_plot_renderer import MotionPlotDetailRenderer`
- Add `MotionPlotDetailRenderer` class from `motion_plot_renderer.py` (lines 1-220) before `MotionTrackDatasource` class
- Update `__all__` to include `'MotionPlotDetailRenderer'`
- Ensure imports are correct (DetailRenderer, ChannelNormalizationMode, etc.)

### Step 2: Update `position.py`

- Remove import: `from pypho_timeline.rendering.detail_renderers import PositionPlotDetailRenderer`
- Add `PositionPlotDetailRenderer` class from `position_plot_renderer.py` (lines 1-126) before `PositionTrackDatasource` class
- Update `__all__` to include `'PositionPlotDetailRenderer'`
- Ensure imports are correct (DetailRenderer, GenericPlotDetailRenderer)

### Step 3: Update `video.py`

- Remove import: `from pypho_timeline.rendering.detail_renderers import VideoThumbnailDetailRenderer`
- Add `VideoThumbnailDetailRenderer` class from `video_thumbnail_renderer.py` (lines 1-188) before `VideoTrackDatasource` class
- Update `__all__` to include `'VideoThumbnailDetailRenderer'`
- Ensure imports are correct (DetailRenderer, GenericPlotDetailRenderer)

### Step 4: Update `datasources/specific/__init__.py`

- Add exports for the renderer classes:
- `from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer`
- `from pypho_timeline.rendering.datasources.specific.position import PositionPlotDetailRenderer`
- `from pypho_timeline.rendering.datasources.specific.video import VideoThumbnailDetailRenderer`
- Update `__all__` to include these classes

### Step 5: Update `detail_renderers/__init__.py`

- Change imports to import from `datasources.specific`:
- `from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer`
- `from pypho_timeline.rendering.datasources.specific.position import PositionPlotDetailRenderer`
- `from pypho_timeline.rendering.datasources.specific.video import VideoThumbnailDetailRenderer`
- Keep generic renderers as-is (GenericPlotDetailRenderer, IntervalPlotDetailRenderer, DataframePlotDetailRenderer, LogTextDataFramePlotDetailRenderer)

### Step 6: Update `rendering/__init__.py`

- Update imports to use new locations (will work through `detail_renderers/__init__.py`)

### Step 7: Update `__main__.py`

- Change import from:
  ```python
      from pypho_timeline.rendering.detail_renderers import MotionPlotDetailRenderer, PositionPlotDetailRenderer, VideoThumbnailDetailRenderer, GenericPlotDetailRenderer
  ```


To:

  ```python
      from pypho_timeline.rendering.detail_renderers import GenericPlotDetailRenderer
      from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer
      from pypho_timeline.rendering.datasources.specific.position import PositionPlotDetailRenderer
      from pypho_timeline.rendering.datasources.specific.video import VideoThumbnailDetailRenderer
  ```

OR keep using `detail_renderers` import (which will re-export from new locations)

### Step 8: Delete Old Renderer Files

- Delete `rendering/detail_renderers/motion_plot_renderer.py`
- Delete `rendering/detail_renderers/position_plot_renderer.py`
- Delete `rendering/detail_renderers/video_thumbnail_renderer.py`

## Files to Modify

1. `rendering/datasources/specific/motion.py` - Add MotionPlotDetailRenderer class
2. `rendering/datasources/specific/position.py` - Add PositionPlotDetailRenderer class
3. `rendering/datasources/specific/video.py` - Add VideoThumbnailDetailRenderer class
4. `rendering/datasources/specific/__init__.py` - Export renderer classes
5. `rendering/detail_renderers/__init__.py` - Update imports to re-export from new locations
6. `__main__.py` - Update imports (optional, can use detail_renderers import)

## Files to Delete

1. `rendering/detail_renderers/motion_plot_renderer.py`
2. `rendering/detail_renderers/position_plot_renderer.py`
3. `rendering/detail_renderers/video_thumbnail_renderer.py`

## Verification

After consolidation:

- All imports should resolve correctly
- `detail_renderers/__init__.py` should re-export the classes for backward compatibility