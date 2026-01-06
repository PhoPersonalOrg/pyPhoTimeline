---
name: Track Settings Button and Channel Visibility
overview: Add a track options/settings button to each track's dock that opens a non-modal dialog allowing users to toggle channel name visibility. The feature will work for tracks with channel-based renderers (EEG, motion, generic plots).
todos: []
---

# Add Track Settings Button and Channel Visibility

## Overview

Add an options button to each track's dock title bar that opens a non-modal dialog for toggling channel visibility. This will work for tracks using channel-based detail renderers (EEG, motion, generic dataframe plots).**Note**: The dock options button functionality already exists in the external library. The Dock automatically shows an options button when a widget provides an options panel via `getOptionsPanel()` method or `optionsPanel` attribute.

## Architecture

The implementation will:

1. Create a `TrackChannelVisibilityOptionsPanel` widget for channel visibility management
2. Implement `getOptionsPanel()` method on `PyqtgraphTimeSynchronizedWidget` to return the options panel
3. Store channel visibility state per track and update renderers accordingly
4. Update detail renderers to respect channel visibility settings
5. Connect options panel changes to update track rendering

## Implementation Details

### 1. Create Track Channel Visibility Options Panel

**New File**: `pypho_timeline/widgets/track_channel_visibility_options_panel.py`

- Create `TrackChannelVisibilityOptionsPanel(QtWidgets.QWidget)` class
- Display list of available channels with checkboxes
- Store visibility state: `Dict[str, bool]` mapping channel name to visibility
- Emit signal when visibility changes: `channelVisibilityChanged = QtCore.Signal(str, bool)` (channel_name, is_visible)
- Initialize with all channels visible by default
- Update checkboxes when visibility state changes externally
- Accept `channel_names: List[str]` in constructor to know which channels to display

### 2. Implement getOptionsPanel() on PyqtgraphTimeSynchronizedWidget

**File**: [`pypho_timeline/core/pyqtgraph_time_synchronized_widget.py`](pypho_timeline/core/pyqtgraph_time_synchronized_widget.py)

- Add `getOptionsPanel()` method that returns `TrackChannelVisibilityOptionsPanel` instance
- Store options panel instance as `self._options_panel` (lazy creation)
- Connect options panel's `channelVisibilityChanged` signal to update handler
- Only create options panel for tracks with channel-based renderers (check if track has channel_names)
- Return `None` if track doesn't support channel visibility (no options button shown)
- Need access to track renderer to get channel names - may need to store reference or query from parent

### 3. Connect Options Panel to Track Renderer

**File**: [`pypho_timeline/docking/specific_dock_widget_mixin.py`](pypho_timeline/docking/specific_dock_widget_mixin.py) or [`pypho_timeline/rendering/mixins/track_rendering_mixin.py`](pypho_timeline/rendering/mixins/track_rendering_mixin.py)

- When track is added, if it has channel-based renderer:
- Get options panel from widget via `getOptionsPanel()`
- Connect panel's `channelVisibilityChanged` signal to track renderer update method
- Store reference to options panel in track renderer or track state
- Pass channel names to options panel from detail renderer

### 4. Store Channel Visibility State

**File**: [`pypho_timeline/rendering/graphics/track_renderer.py`](pypho_timeline/rendering/graphics/track_renderer.py)

- Add `channel_visibility: Dict[str, bool] `to `TrackRenderer.__init__`
- Initialize visibility: all channels visible by default (`{channel: True for channel in channel_names}`)
- Add method `update_channel_visibility(channel_name: str, is_visible: bool)` to update state
- When visibility changes, clear and re-render all visible detail graphics
- Store reference to options panel if available for bidirectional updates
- Get channel names from `self.detail_renderer.channel_names` during initialization

### 5. Update Detail Renderers to Respect Visibility

**Files**:

- [`pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py)
- [`pypho_timeline/rendering/detail_renderers/motion_plot_renderer.py`](pypho_timeline/rendering/detail_renderers/motion_plot_renderer.py)
- [`pypho_timeline/rendering/datasources/specific/eeg.py`](pypho_timeline/rendering/datasources/specific/eeg.py)
- Modify `render_detail` methods to filter `channel_names_to_use` based on visibility state
- Get visibility state from `TrackRenderer` (passed via datasource or renderer context)
- Only render channels where `channel_visibility.get(channel_name, True) == True`
- Need to pass `channel_visibility` dict from TrackRenderer to detail renderer
- Options: pass as parameter to `render_detail`, or store in detail renderer instance, or access via track_renderer reference

## Data Flow

```javascript
User clicks options button (automatically shown by Dock when widget provides options panel)
  → Dock calls widget.getOptionsPanel()
  → Returns TrackChannelVisibilityOptionsPanel
  → Dock opens non-modal dialog with options panel
  → User toggles channel checkbox
  → Options panel emits channelVisibilityChanged signal
  → TrackRenderer.update_channel_visibility() updates channel_visibility dict
  → TrackRenderer clears and re-renders all visible detail graphics
  → Detail renderer filters channels based on visibility state
  → Plot updates with only visible channels
```



## Key Considerations

1. **Button Visibility**: Options button is automatically shown by Dock when widget provides `getOptionsPanel()` returning a non-None widget. No manual button configuration needed.
2. **Dialog Type**: Dock automatically creates a non-modal dialog with OK/Cancel buttons. The options panel widget is embedded in this dialog.
3. **State Management**: Channel visibility state stored per track in `TrackRenderer`, persists for track lifetime
4. **Renderer Compatibility**: Only create options panel for tracks with channel-based renderers (check `detail_renderer.channel_names` exists and is not None)
5. **Default Behavior**: All channels visible by default; options panel checkboxes reflect current state
6. **Re-rendering**: When visibility changes, `TrackRenderer` should clear all detail graphics and re-render visible intervals with filtered channel set
7. **Channel Name Source**: Options panel needs channel names - get from `track_renderer.detail_renderer.channel_names` or auto-detect from first detail data fetch
8. **Widget-to-Renderer Connection**: `PyqtgraphTimeSynchronizedWidget` needs access to `TrackRenderer` to get channel names and update visibility. May need to store reference or use signal/slot pattern.

## Testing Points

- Options button automatically appears on track docks with channel-based renderers (when widget provides options panel)
- Clicking button opens non-modal dialog with options panel
- Channel checkboxes reflect current visibility state
- Toggling checkboxes immediately updates plot
- Dialog can remain open while interacting with timeline
- Options panel only created for tracks with channel-based renderers (no button for other tracks)
- Visibility state persists for track lifetime