---
name: Base Options Panel Architecture
overview: Create a base OptionsPanel widget and PanelOwningMixin that handle common panel functionality, allowing TrackChannelVisibilityOptionsPanel and TrackOptionsPanelOwningMixin to inherit from them. This enables tracks without channels (like pure interval tracks) to use a basic options panel.
todos: []
---

# Base Options Panel Architecture

## Overview

Refactor the options panel system to introduce base classes that handle common panel functionality (showing/hiding, callbacks, UI structure), allowing specific implementations like `TrackChannelVisibilityOptionsPanel` to focus on their custom widgets and configuration logic.

## Current State

- `TrackChannelVisibilityOptionsPanel` is a standalone widget for channel visibility
- `TrackOptionsPanelOwningMixin` manages the options panel lifecycle
- Only tracks with `channel_names` in their detail renderer get options panels (see `PyqtgraphTimeSynchronizedWidget.getOptionsPanel()` lines 585-586)
- Tracks without channels (e.g., `IntervalPlotDetailRenderer`, `VideoThumbnailDetailRenderer`, `GenericPlotDetailRenderer`) have no options panel support

## Architecture Changes

### 1. Create Base OptionsPanel Widget

**File**: `pyPhoTimeline/pypho_timeline/widgets/track_channel_visibility_options_panel.py`Create a base `OptionsPanel` class that:

- Inherits from `QtWidgets.QWidget`
- Provides basic UI structure: title label, scroll area, content widget
- Defines abstract/virtual methods for subclasses to override:
- `_build_content_widget()`: Subclasses implement to add their specific widgets
- `_get_panel_title()`: Subclasses override to customize title (default: "Options")
- Handles common panel functionality (showing, hiding, layout management)
- Emits a generic `optionsChanged` signal that subclasses can use or extend

### 2. Create Base PanelOwningMixin

**File**: `pyPhoTimeline/pypho_timeline/widgets/track_channel_visibility_options_panel.py`Create a base `PanelOwningMixin` class that:

- Provides `options_panel` property (getter/setter) that stores panel in `self.ui.options_panel`
- Defines lifecycle hooks:
- `PanelOwningMixin_on_init()`: Initialize panel state
- `PanelOwningMixin_on_setup()`: Setup phase
- `PanelOwningMixin_on_buildUI()`: Initialize `self.ui.options_panel = None`
- `PanelOwningMixin_on_destroy()`: Cleanup
- Requires implementors to have `self.ui` attribute

### 3. Refactor TrackChannelVisibilityOptionsPanel

**File**: `pyPhoTimeline/pypho_timeline/widgets/track_channel_visibility_options_panel.py`

- Make `TrackChannelVisibilityOptionsPanel` inherit from `OptionsPanel`
- Override `_build_content_widget()` to create channel checkboxes
- Override `_get_panel_title()` to return "Channel Visibility"
- Keep `channelVisibilityChanged` signal (can also emit base `optionsChanged` if needed)
- Move channel-specific logic into the content widget building method

### 4. Refactor TrackOptionsPanelOwningMixin

**File**: `pyPhoTimeline/pypho_timeline/widgets/track_channel_visibility_options_panel.py`

- Make `TrackOptionsPanelOwningMixin` inherit from `PanelOwningMixin`
- Keep existing functionality (no changes needed, just inheritance)

### 5. Update PyqtgraphTimeSynchronizedWidget

**File**: `pyPhoTimeline/pypho_timeline/core/pyqtgraph_time_synchronized_widget.py`Update `getOptionsPanel()` method (lines 573-608):

- For tracks with channels: Create `TrackChannelVisibilityOptionsPanel` (existing behavior)
- For tracks without channels: Create basic `OptionsPanel` instance (new capability)
- This allows all tracks to have an options panel, even if empty/basic

## Implementation Details

### Base OptionsPanel Structure

```python
class OptionsPanel(QtWidgets.QWidget):
    """Base options panel widget for track configuration.
    
    Provides common UI structure and lifecycle management. Subclasses
    should override _build_content_widget() to add their specific options.
    """
    
    # Generic signal emitted when any option changes
    optionsChanged = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the base UI structure."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Title
        title_label = QtWidgets.QLabel(self._get_panel_title())
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Scroll area for content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        scroll_area.setMaximumHeight(400)
        
        content_widget = self._build_content_widget()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
    
    def _get_panel_title(self) -> str:
        """Get the panel title. Override in subclasses."""
        return "Options"
    
    def _build_content_widget(self) -> QtWidgets.QWidget:
        """Build the content widget. Must be overridden by subclasses."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        layout.addStretch()  # Empty by default
        return widget
```



### Base PanelOwningMixin Structure

```python
class PanelOwningMixin:
    """Base mixin for classes that own an options panel.
    
    Provides common panel management functionality. Requires:
    - self.ui attribute (PhoUIContainer or similar)
    """
    
    @property
    def options_panel(self):
        return self.ui.options_panel
    
    @options_panel.setter
    def options_panel(self, value):
        self.ui.options_panel = value
    
    def PanelOwningMixin_on_init(self):
        """Initialize panel state during __init__."""
        pass
    
    def PanelOwningMixin_on_setup(self):
        """Setup phase - core objects exist."""
        pass
    
    def PanelOwningMixin_on_buildUI(self):
        """Build UI phase - initialize options_panel."""
        assert hasattr(self, 'ui')
        assert self.ui is not None
        self.ui.options_panel = None
    
    def PanelOwningMixin_on_destroy(self):
        """Cleanup phase."""
        pass
```



## Files to Modify

1. **pyPhoTimeline/pypho_timeline/widgets/track_channel_visibility_options_panel.py**

- Add `OptionsPanel` base class
- Add `PanelOwningMixin` base class
- Refactor `TrackChannelVisibilityOptionsPanel` to inherit from `OptionsPanel`
- Refactor `TrackOptionsPanelOwningMixin` to inherit from `PanelOwningMixin`

2. **pyPhoTimeline/pypho_timeline/core/pyqtgraph_time_synchronized_widget.py**

- Update `getOptionsPanel()` to create basic `OptionsPanel` for tracks without channels

3. **pyPhoTimeline/pypho_timeline/core/time_synchronized_plotter_base.py**

- No changes needed (already uses `TrackOptionsPanelOwningMixin`)

## Benefits

- **Reusability**: Base classes can be used for any track type
- **Extensibility**: Easy to add new options panel types (e.g., video playback controls, interval styling)
- **Consistency**: All options panels share the same UI structure and lifecycle
- **Flexibility**: Tracks without channels can still have an options panel (even if empty initially)