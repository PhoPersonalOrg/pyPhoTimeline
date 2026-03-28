"""Track Options Panels - Options panels for track configuration."""
from typing import Any, List, Dict, Optional

from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from qtpy import QtCore, QtWidgets

from pypho_timeline.utils.logging_util import get_rendering_logger

logger = get_rendering_logger(__name__)

TRACK_OPTIONS_CONFIG_VERSION = 1
TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY = "channel_visibility"

# Base Options Panel _______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
class OptionsPanel(QtWidgets.QWidget):
    """Base options panel widget for track configuration.
    
    Provides common UI structure and lifecycle management. Subclasses
    should override _build_content_widget() to add their specific options.
    
    Usage:
        # Basic empty panel
        panel = OptionsPanel()
        
        # Custom panel
        class MyOptionsPanel(OptionsPanel):
            def _get_panel_title(self) -> str:
                return "My Options"
            
            def _build_content_widget(self) -> QtWidgets.QWidget:
                widget = QtWidgets.QWidget()
                layout = QtWidgets.QVBoxLayout(widget)
                layout.setContentsMargins(5, 5, 5, 5)
                layout.setSpacing(3)
                # Add custom widgets here
                layout.addWidget(QtWidgets.QLabel("Custom content"))
                layout.addStretch()
                return widget
    """
    
    # Generic signal emitted when any option changes
    optionsChanged = QtCore.Signal()
    onOptionsAccepted = QtCore.Signal()
    onOptionsRejected = QtCore.Signal()
    
    def __init__(self, parent=None):
        """Initialize the base options panel.
        
        Args:
            parent: Parent widget
        """
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
        """Get the panel title. Override in subclasses.
        
        Returns:
            Panel title string
        """
        return "Options"
    
    def _build_content_widget(self) -> QtWidgets.QWidget:
        """Build the content widget. Must be overridden by subclasses.
        
        Returns:
            QWidget containing the panel's content
        """
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        layout.addStretch()  # Empty by default
        return widget


    def track_options_kind(self) -> Optional[str]:
        """Return a stable kind string for serialized track options, or None if none."""
        return None


    def dump_track_options_state(self) -> Optional[Dict[str, Any]]:
        """Return a per-track options payload dict for this panel, or None."""
        return None


    def apply_track_options_state(self, data: Dict[str, Any]) -> None:
        """Apply a payload from :meth:`dump_track_options_state` (default: no-op)."""
        pass


    # Options Panel Implementation _______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
    @pyqtExceptionPrintingSlot()
    def on_options_changed(self):
        """Emit optionsChanged signal when any option changes."""
        print(f'.on_options_changed()')
        self.optionsChanged.emit()


    @pyqtExceptionPrintingSlot()
    def on_options_accepted(self):
        """Emit onOptionsAccepted signal when options are accepted."""
        print(f'.on_options_accepted()')
        self.onOptionsAccepted.emit()


    @pyqtExceptionPrintingSlot()
    def on_options_rejected(self):
        """Emit onOptionsRejected signal when options are rejected."""
        print(f'.on_options_rejected()')
        self.onOptionsRejected.emit()




# Channel Visibility Options Panel _______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
class TrackChannelVisibilityOptionsPanel(OptionsPanel):
    """Options panel widget for managing channel visibility in timeline tracks.
    
    Displays a list of checkboxes for each channel, allowing users to toggle
    which channels are visible in the track's detail view.
    
    Usage:
        panel = TrackChannelVisibilityOptionsPanel(channel_names=['x', 'y', 'z'])
        panel.channelVisibilityChanged.connect(on_visibility_changed)
    """
    # Signal emitted when a channel's visibility changes
    # Args: (channel_name: str, is_visible: bool)
    channelVisibilityChanged = QtCore.Signal(str, bool)
    

    def __init__(self, channel_names: List[str], initial_visibility: Optional[Dict[str, bool]] = None, parent=None):
        """Initialize the channel visibility options panel.
        
        Args:
            channel_names: List of channel names to display
            initial_visibility: Optional dict mapping channel names to visibility state.
                              If None, all channels are visible by default.
            parent: Parent widget
        """
        self.channel_names = channel_names
        self._checkboxes: Dict[str, QtWidgets.QCheckBox] = {}
        
        # Initialize visibility state (all visible by default)
        if initial_visibility is None:
            self._visibility_state = {channel: True for channel in channel_names}
        else:
            self._visibility_state = initial_visibility.copy()
            # Ensure all channels are in the dict
            for channel in channel_names:
                if channel not in self._visibility_state:
                    self._visibility_state[channel] = True
        
        super().__init__(parent)
    
    def _get_panel_title(self) -> str:
        """Get the panel title.
        
        Returns:
            Panel title string
        """
        return "Channel Visibility"
    
    def _build_content_widget(self) -> QtWidgets.QWidget:
        """Build the content widget with channel checkboxes.
        
        Returns:
            QWidget containing channel checkboxes
        """
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(3)
        
        # Create checkbox for each channel
        for channel_name in self.channel_names:
            checkbox = QtWidgets.QCheckBox(channel_name)
            checkbox.setChecked(self._visibility_state.get(channel_name, True))
            # Use a lambda that captures channel_name correctly
            checkbox.stateChanged.connect(lambda state, ch=channel_name: self._on_checkbox_changed(ch, state))
            self._checkboxes[channel_name] = checkbox
            scroll_layout.addWidget(checkbox)
        
        # Add stretch to push checkboxes to top
        scroll_layout.addStretch()
        
        return scroll_widget
    
    def _on_checkbox_changed(self, channel_name: str, state):
        """Handle checkbox state change.
        
        Args:
            channel_name: Name of the channel
            state: Value from QCheckBox.stateChanged (compare to QtCore.Qt.CheckState.Checked)
        """
        is_visible = state == QtCore.Qt.CheckState.Checked
        self._visibility_state[channel_name] = is_visible
        self.channelVisibilityChanged.emit(channel_name, is_visible)
        self.optionsChanged.emit()  # Also emit base signal
    
    def get_visibility_state(self) -> Dict[str, bool]:
        """Get the current visibility state for all channels.
        
        Returns:
            Dict mapping channel names to visibility (True = visible, False = hidden)
        """
        return self._visibility_state.copy()
    
    def set_visibility_state(self, visibility_state: Dict[str, bool], emit_signals: bool = False):
        """Update the visibility state from external source.
        
        Args:
            visibility_state: Dict mapping channel names to visibility
            emit_signals: If True, emit channelVisibilityChanged signals for changed channels
        """
        old_state = self._visibility_state.copy()
        self._visibility_state.update(visibility_state)
        
        # Update checkboxes
        for channel_name, is_visible in visibility_state.items():
            if channel_name in self._checkboxes:
                # Block signals during update to avoid emitting if emit_signals=False
                checkbox = self._checkboxes[channel_name]
                checkbox.blockSignals(True)
                checkbox.setChecked(is_visible)
                checkbox.blockSignals(False)
                
                # Emit signal if requested and state changed
                if emit_signals and old_state.get(channel_name) != is_visible:
                    self.channelVisibilityChanged.emit(channel_name, is_visible)
    
    def is_channel_visible(self, channel_name: str) -> bool:
        """Check if a channel is currently visible.
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            True if channel is visible, False otherwise
        """
        return self._visibility_state.get(channel_name, True)


    def track_options_kind(self) -> Optional[str]:
        return TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY


    def dump_track_options_state(self) -> Optional[Dict[str, Any]]:
        return {"kind": TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY, "channel_visibility": self.get_visibility_state()}


    def apply_track_options_state(self, data: Dict[str, Any]) -> None:
        if data.get("kind") != TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY:
            return
        vis = data.get("channel_visibility")
        if isinstance(vis, dict):
            self.set_visibility_state({k: bool(v) for k, v in vis.items()}, emit_signals=False)


def build_track_options_document(track_renderers: Dict[str, Any]) -> Dict[str, Any]:
    """Build a versioned document from each renderer's ``channel_visibility`` (omit non-channel tracks)."""
    tracks: Dict[str, Any] = {}
    for name, renderer in track_renderers.items():
        cv = getattr(renderer, "channel_visibility", None) or {}
        if not cv:
            continue
        tracks[name] = {"kind": TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY, "channel_visibility": {k: bool(v) for k, v in cv.items()}}
    return {"version": TRACK_OPTIONS_CONFIG_VERSION, "tracks": tracks}


def apply_track_options_document(doc: Dict[str, Any], track_renderers: Dict[str, Any]) -> None:
    """Apply a document from :func:`build_track_options_document`; unknown tracks and kinds are skipped."""
    if not isinstance(doc, dict):
        logger.warning("apply_track_options_document: expected dict root")
        return
    ver = doc.get("version")
    if ver is not None and ver != TRACK_OPTIONS_CONFIG_VERSION:
        logger.info("apply_track_options_document: version %r != %s, applying compatible entries only", ver, TRACK_OPTIONS_CONFIG_VERSION)
    tracks = doc.get("tracks")
    if not isinstance(tracks, dict):
        return
    for track_name, entry in tracks.items():
        renderer = track_renderers.get(track_name)
        if renderer is None:
            logger.debug("apply_track_options_document: skip unknown track %r", track_name)
            continue
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY:
            vis = entry.get("channel_visibility")
            if isinstance(vis, dict):
                renderer.apply_channel_visibility_bulk({k: bool(v) for k, v in vis.items()})
        else:
            logger.debug("apply_track_options_document: skip unknown kind %r for track %r", kind, track_name)


# Track Options Panel Owning Mixin _______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
class TrackOptionsPanelOwningMixin:
    """Implementors own an options panel which allows them to customize their configuration.
    
    This mixin is used by timeline widgets that need to manage options panels for their tracks.
    
    Requires at minimum:
        - self.ui attribute (PhoUIContainer or similar)
        
    Creates:
        - options_panel property (getter/setter)
        - Lifecycle hooks: TrackOptionsPanelOwningMixin_on_init, _on_setup, _on_buildUI, _on_destroy
        
    Known Usages:
        - TimeSynchronizedPlotterBase
        - PyqtgraphTimeSynchronizedWidget
        
    Signals:
        # TrackOptionsPanelOwningMixin Conformance Signals _____________________________________________________________ #
        # sigSignalName = QtCore.Signal(object) # (param1, param2)
        
    Usage:
        from pypho_timeline.widgets.track_options_panels import TrackChannelVisibilityOptionsPanel, TrackOptionsPanelOwningMixin
    """
    optionsChanged = QtCore.Signal()
    onOptionsAccepted = QtCore.Signal()
    onOptionsRejected = QtCore.Signal()

    @property
    def options_panel(self):
        """Get the options panel widget."""
        return self.ui.options_panel
    
    @options_panel.setter
    def options_panel(self, value):
        """Set the options panel widget."""
        self.ui.options_panel = value
    
    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        pass
    
    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_setup(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        pass
    
    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_buildUI(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        assert hasattr(self, 'ui')
        assert self.ui is not None
        self.ui.options_panel = None


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_optionsChanged(self):
        """Emit optionsChanged signal when options change."""
        logger.info(f"TrackOptionsPanelOwningMixin[{self}] TrackOptionsPanelOwningMixin_optionsChanged()")
        print(f'TrackOptionsPanelOwningMixin_optionsChanged()')
        self.optionsChanged.emit()
        logger.info(f"\t emitted self.optionsChanged()")


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_onOptionsAccepted(self):
        """Emit onOptionsAccepted signal when options are accepted."""
        logger.info(f"TrackOptionsPanelOwningMixin[{self}] TrackOptionsPanelOwningMixin_onOptionsAccepted()")
        print(f'TrackOptionsPanelOwningMixin_onOptionsAccepted()')
        self.onOptionsAccepted.emit()
        logger.info(f"\t emitted self.onOptionsAccepted()")


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_onOptionsRejected(self):
        """Emit onOptionsRejected signal when options are rejected."""
        logger.info(f"TrackOptionsPanelOwningMixin[{self}] TrackOptionsPanelOwningMixin_onOptionsRejected()")
        print(f'TrackOptionsPanelOwningMixin_onOptionsRejected()')
        self.onOptionsRejected.emit()
        logger.info(f"\t emitted self.onOptionsRejected()")





__all__ = [
    "OptionsPanel",
    "TrackChannelVisibilityOptionsPanel",
    "TrackOptionsPanelOwningMixin",
    "TRACK_OPTIONS_CONFIG_VERSION",
    "TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY",
    "build_track_options_document",
    "apply_track_options_document",
]

