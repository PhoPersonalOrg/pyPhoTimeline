"""TrackChannelVisibilityOptionsPanel - Options panel for toggling channel visibility in tracks."""
from typing import Any, List, Dict, Optional
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from qtpy import QtCore, QtWidgets


class TrackChannelVisibilityOptionsPanel(QtWidgets.QWidget):
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
        super().__init__(parent)
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
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Title label
        title_label = QtWidgets.QLabel("Channel Visibility")
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Scroll area for channel checkboxes
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        scroll_area.setMaximumHeight(400)
        
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
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def _on_checkbox_changed(self, channel_name: str, check_state):
        """Handle checkbox state change.
        
        Args:
            channel_name: Name of the channel
            check_state: Qt check state (QtCore.Qt.CheckState.Checked or Unchecked)
        """
        is_visible = (check_state == QtCore.Qt.CheckState.Checked)
        self._visibility_state[channel_name] = is_visible
        self.channelVisibilityChanged.emit(channel_name, is_visible)
    
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



# class TrackOptionsPanelOwningMixin(QtCore.QObject):
class TrackOptionsPanelOwningMixin:
    """ Implementors own an options panel which allows them to customize their configuration
    
    Requires at minimum:
        List of required attributes/methods
        self.ui
        
    Creates:
        List of attributes/methods this mixin creates
        
        
    Known Usages:
        List of classes that use this mixin
    
    Signals:
        # TrackOptionsPanelOwningMixin Conformance Signals _____________________________________________________________ #
        # sigSignalName = QtCore.Signal(object) # (param1, param2)
        

        from pypho_timeline.widgets.track_channel_visibility_options_panel import TrackChannelVisibilityOptionsPanel, TrackOptionsPanelOwningMixin

    """
    # def __init__(self, track_renderer: Optional[Any]=None, options_panel: Optional[QtWidgets.QWidget]=None, parent=None, **kwargs):
    #     """ the __init__ form allows adding menus to extant widgets without modifying their class to inherit from this mixin """
    #     super(TrackOptionsPanelOwningMixin, self).__init__(parent)
    #     # Setup member variables:
    #     # Assumes that self is a QWidget subclass:
    #     self._track_renderer = track_renderer # do we really need a reference to this?
    #     self._options_panel = options_panel

    @property
    def options_panel(self):
        return self.ui.options_panel

   
    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_init(self):
        """ perform any parameters setting/checking during init """
        # self._options_panel = None
        # self._track_renderer = None # do we really need a reference to this?
        pass

    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_setup(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        pass


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_buildUI(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        assert hasattr(self, 'ui')
        assert self.ui is not None
        self.ui.options_panel = None ## initialize


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_destroy(self):
        """ perform teardown/destruction of anything that needs to be manually removed or released """
        pass


    def getOptionsPanel(self):
        """Get the options panel for this widget.
        
        Returns:
            QWidget with options panel, or None if not applicable
        """
        # Only create options panel for tracks with channel-based renderers
        if self._track_renderer is None:
            return None
        
        # Check if detail renderer has channel_names
        detail_renderer = self._track_renderer.detail_renderer
        if not hasattr(detail_renderer, 'channel_names') or detail_renderer.channel_names is None:
            return None
        
        # Create options panel if not already created
        if self.options_panel is None:
            from pypho_timeline.widgets.track_channel_visibility_options_panel import TrackChannelVisibilityOptionsPanel
            
            channel_names = detail_renderer.channel_names
            initial_visibility = self._track_renderer.channel_visibility.copy()
            
            self.options_panel = TrackChannelVisibilityOptionsPanel(
                channel_names=channel_names,
                initial_visibility=initial_visibility
            )
            
            # Connect panel signals to track renderer
            self.options_panel.channelVisibilityChanged.connect(
                self._track_renderer.update_channel_visibility
            )
            
            # Store reference in track renderer for bidirectional updates
            self._track_renderer.set_options_panel(self.options_panel)
        
        return self.options_panel


class TrackOptionsPanelOwningMixin:
    """ Implementors own an options panel which allows them to customize their configuration
    
    Requires at minimum:
        List of required attributes/methods
        self.ui
        
    Creates:
        List of attributes/methods this mixin creates
        
        
    Known Usages:
        List of classes that use this mixin
    
    Signals:
        # TrackOptionsPanelOwningMixin Conformance Signals _____________________________________________________________ #
        # sigSignalName = QtCore.Signal(object) # (param1, param2)
        

        from pypho_timeline.widgets.track_channel_visibility_options_panel import TrackChannelVisibilityOptionsPanel, TrackOptionsPanelOwningMixin

    """
    # def __init__(self, track_renderer: Optional[Any]=None, options_panel: Optional[QtWidgets.QWidget]=None, parent=None, **kwargs):
    #     """ the __init__ form allows adding menus to extant widgets without modifying their class to inherit from this mixin """
    #     super(TrackOptionsPanelOwningMixin, self).__init__(parent)
    #     # Setup member variables:
    #     # Assumes that self is a QWidget subclass:
    #     self._track_renderer = track_renderer # do we really need a reference to this?
    #     self._options_panel = options_panel

    @property
    def options_panel(self):
        return self.ui.options_panel
    @options_panel.setter
    def options_panel(self, value):
        self.ui.options_panel = value

   
    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_init(self):
        """ perform any parameters setting/checking during init """
        # self._options_panel = None
        # self._track_renderer = None # do we really need a reference to this?
        pass

    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_setup(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        pass


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_buildUI(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        assert hasattr(self, 'ui')
        assert self.ui is not None
        self.ui.options_panel = None ## initialize


    @pyqtExceptionPrintingSlot()
    def TrackOptionsPanelOwningMixin_on_destroy(self):
        """ perform teardown/destruction of anything that needs to be manually removed or released """
        pass



__all__ = ['TrackChannelVisibilityOptionsPanel', 'TrackOptionsPanelOwningMixin']
