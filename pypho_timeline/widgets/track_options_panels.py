"""Track Options Panels - Options panels for track configuration."""
from typing import Any, List, Dict, Optional
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from qtpy import QtCore, QtWidgets


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
            checkbox.stateChanged.connect(
                lambda state, ch=channel_name: self._on_checkbox_changed(ch, state == QtCore.Qt.CheckState.Checked)
            )
            self._checkboxes[channel_name] = checkbox
            scroll_layout.addWidget(checkbox)
        
        # Add stretch to push checkboxes to top
        scroll_layout.addStretch()
        
        return scroll_widget
    
    def _on_checkbox_changed(self, channel_name: str, check_state):
        """Handle checkbox state change.
        
        Args:
            channel_name: Name of the channel
            check_state: Qt check state (QtCore.Qt.CheckState.Checked or Unchecked)
        """
        is_visible = (check_state == QtCore.Qt.CheckState.Checked)
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
        self.optionsChanged.emit()

    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_onOptionsAccepted(self):
        """Emit onOptionsAccepted signal when options are accepted."""
        self.onOptionsAccepted.emit()


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_onOptionsRejected(self):
        """Emit onOptionsRejected signal when options are rejected."""
        self.onOptionsRejected.emit()





__all__ = ['OptionsPanel', 'TrackChannelVisibilityOptionsPanel', 'TrackOptionsPanelOwningMixin']

