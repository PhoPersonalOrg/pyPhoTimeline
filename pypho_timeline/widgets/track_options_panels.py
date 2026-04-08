"""Track Options Panels - Options panels for track configuration."""
from typing import Any, List, Dict, Optional

from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from qtpy import QtCore, QtWidgets

from pypho_timeline.utils.logging_util import get_rendering_logger

logger = get_rendering_logger(__name__)

TRACK_OPTIONS_CONFIG_VERSION = 1
TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY = "channel_visibility"
TRACK_OPTIONS_KIND_EEG_SPECTROGRAM = "eeg_spectrogram"
TRACK_OPTIONS_KIND_LINE_POWER_GFP = "line_power_gfp"

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


class EEGSpectrogramTrackOptionsPanel(OptionsPanel):
    """Options panel for EEG spectrogram tracks: frequency range, preset group, per-channel inclusion in average."""

    spectrogramOptionsApplied = QtCore.Signal()


    def __init__(self, track_renderer: Any, parent=None):
        self._track_renderer = track_renderer
        self._ds: Any = track_renderer.datasource
        self._freq_min_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._freq_max_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._preset_combo: Optional[QtWidgets.QComboBox] = None
        self._channels_layout: Optional[QtWidgets.QVBoxLayout] = None
        self._ch_checkboxes: Dict[str, QtWidgets.QCheckBox] = {}
        super().__init__(parent)


    def _get_panel_title(self) -> str:
        return "EEG spectrogram"


    def _build_content_widget(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        freq_row = QtWidgets.QHBoxLayout()
        freq_row.addWidget(QtWidgets.QLabel("Freq min (Hz):"))
        self._freq_min_spin = QtWidgets.QDoubleSpinBox()
        self._freq_min_spin.setRange(0.5, 200.0)
        self._freq_min_spin.setSingleStep(0.5)
        self._freq_min_spin.setValue(float(self._ds.spectrogram_freq_min))
        self._freq_min_spin.valueChanged.connect(self._on_freq_or_channels_applied)
        freq_row.addWidget(self._freq_min_spin)
        freq_row.addWidget(QtWidgets.QLabel("max:"))
        self._freq_max_spin = QtWidgets.QDoubleSpinBox()
        self._freq_max_spin.setRange(0.5, 200.0)
        self._freq_max_spin.setSingleStep(0.5)
        self._freq_max_spin.setValue(float(self._ds.spectrogram_freq_max))
        self._freq_max_spin.valueChanged.connect(self._on_freq_or_channels_applied)
        freq_row.addWidget(self._freq_max_spin)
        freq_row.addStretch()
        layout.addLayout(freq_row)
        presets = self._ds.channel_group_presets
        if presets is not None and len(presets) > 1:
            preset_row = QtWidgets.QHBoxLayout()
            preset_row.addWidget(QtWidgets.QLabel("Group preset:"))
            self._preset_combo = QtWidgets.QComboBox()
            self._preset_combo.addItem("(All channels)")
            for p in presets:
                self._preset_combo.addItem(p.name)
            self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
            preset_row.addWidget(self._preset_combo, stretch=1)
            layout.addLayout(preset_row)
        layout.addWidget(QtWidgets.QLabel("Channels in average:"))
        ch_host = QtWidgets.QWidget()
        self._channels_layout = QtWidgets.QVBoxLayout(ch_host)
        self._channels_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(ch_host)
        self._rebuild_channel_checkboxes()
        self._sync_preset_combo_index()
        layout.addStretch()
        return root


    def _sync_preset_combo_index(self) -> None:
        if self._preset_combo is None:
            return
        presets = self._ds.channel_group_presets
        if not presets:
            return
        gc = self._ds.group_config
        self._preset_combo.blockSignals(True)
        if gc is None:
            self._preset_combo.setCurrentIndex(0)
        else:
            names = [p.name for p in presets]
            idx = 1 + names.index(gc.name) if gc.name in names else 0
            self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)


    def _base_channel_names_for_ui(self) -> List[str]:
        avail = set(self._ds.get_spectrogram_ch_names())
        gc = self._ds.group_config
        if gc is not None:
            return [ch for ch in gc.channels if ch in avail]
        return sorted(avail)


    def _rebuild_channel_checkboxes(self) -> None:
        if self._channels_layout is None:
            return
        while self._channels_layout.count():
            item = self._channels_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._ch_checkboxes.clear()
        names = self._base_channel_names_for_ui()
        gc = self._ds.group_config
        if gc is None and not names:
            return
        active_set = set(names) if gc is None else set(gc.channels) & set(names)
        for ch in names:
            cb = QtWidgets.QCheckBox(ch)
            cb.setChecked(ch in active_set)
            cb.stateChanged.connect(lambda _st, c=ch: self._on_channel_checkbox_changed(c))
            self._ch_checkboxes[ch] = cb
            self._channels_layout.addWidget(cb)


    @pyqtExceptionPrintingSlot()
    def _on_preset_index_changed(self, index: int) -> None:
        presets = self._ds.channel_group_presets
        if presets is None or index < 0 or index > len(presets):
            return
        if index == 0:
            self._ds.set_group_config(None)
        else:
            self._ds.set_group_config(presets[index - 1])
        self._rebuild_channel_checkboxes()
        self._apply_all_to_datasource()


    @pyqtExceptionPrintingSlot()
    def _on_channel_checkbox_changed(self, channel_name: str) -> None:
        from pypho_timeline.rendering.datasources.specific.eeg import SpectrogramChannelGroupConfig as _SpectrogramChannelGroupConfig
        cb = self._ch_checkboxes.get(channel_name)
        if cb is None:
            return
        checked = [ch for ch, cbox in self._ch_checkboxes.items() if cbox.isChecked()]
        if not checked:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
            return
        avail = set(self._ds.get_spectrogram_ch_names())
        all_avail = sorted(avail)
        gc = self._ds.group_config
        if gc is None and set(checked) == set(all_avail) and len(all_avail) > 0:
            self._ds.set_group_config(None)
        else:
            name = gc.name if gc is not None else "Custom"
            self._ds.set_group_config(_SpectrogramChannelGroupConfig(name=name, channels=checked))
        self._apply_all_to_datasource()
        self._sync_preset_combo_index()


    @pyqtExceptionPrintingSlot()
    def _on_freq_or_channels_applied(self) -> None:
        if self._freq_min_spin is None or self._freq_max_spin is None:
            return
        lo, hi = float(self._freq_min_spin.value()), float(self._freq_max_spin.value())
        if lo > hi:
            self._freq_min_spin.blockSignals(True)
            self._freq_max_spin.blockSignals(True)
            self._freq_min_spin.setValue(hi)
            self._freq_max_spin.setValue(lo)
            lo, hi = float(self._freq_min_spin.value()), float(self._freq_max_spin.value())
            self._freq_min_spin.blockSignals(False)
            self._freq_max_spin.blockSignals(False)
        self._apply_all_to_datasource()


    def _apply_all_to_datasource(self) -> None:
        if self._freq_min_spin is None or self._freq_max_spin is None:
            return
        self._ds.set_spectrogram_display(float(self._freq_min_spin.value()), float(self._freq_max_spin.value()))
        self.spectrogramOptionsApplied.emit()
        self.optionsChanged.emit()


    def track_options_kind(self) -> Optional[str]:
        return TRACK_OPTIONS_KIND_EEG_SPECTROGRAM


    def dump_track_options_state(self) -> Optional[Dict[str, Any]]:
        gc = self._ds.group_config
        return {"kind": TRACK_OPTIONS_KIND_EEG_SPECTROGRAM, "freq_min": float(self._ds.spectrogram_freq_min), "freq_max": float(self._ds.spectrogram_freq_max),
                "group_name": (gc.name if gc else None), "channels": (list(gc.channels) if gc else None)}


    def apply_track_options_state(self, data: Dict[str, Any]) -> None:
        from pypho_timeline.rendering.datasources.specific.eeg import SpectrogramChannelGroupConfig as _SpectrogramChannelGroupConfig
        if data.get("kind") != TRACK_OPTIONS_KIND_EEG_SPECTROGRAM:
            return
        fmin = data.get("freq_min")
        fmax = data.get("freq_max")
        if fmin is not None and fmax is not None:
            self._ds.set_spectrogram_display(float(fmin), float(fmax))
            if self._freq_min_spin is not None:
                self._freq_min_spin.blockSignals(True)
                self._freq_max_spin.blockSignals(True)
                self._freq_min_spin.setValue(float(fmin))
                self._freq_max_spin.setValue(float(fmax))
                self._freq_min_spin.blockSignals(False)
                self._freq_max_spin.blockSignals(False)
        gname = data.get("group_name")
        chans = data.get("channels")
        presets = self._ds.channel_group_presets
        if chans is None and gname is None:
            self._ds.set_group_config(None)
        elif isinstance(chans, list) and chans:
            self._ds.set_group_config(_SpectrogramChannelGroupConfig(name=str(gname) if gname else "Custom", channels=[str(c) for c in chans]))
        elif gname and presets:
            match = next((p for p in presets if p.name == gname), None)
            if match is not None:
                self._ds.set_group_config(match)
        self._sync_preset_combo_index()
        self._rebuild_channel_checkboxes()
        self.spectrogramOptionsApplied.emit()
        self.optionsChanged.emit()


class LinePowerGFPTrackOptionsPanel(OptionsPanel):
    """Options panel for :class:`~pypho_timeline.rendering.datasources.specific.eeg.EEGFPTrackDatasource` (band-limited GFP lanes)."""

    gfpOptionsApplied = QtCore.Signal()


    def __init__(self, track_renderer: Any, parent=None):
        self._track_renderer = track_renderer
        self._ds: Any = track_renderer.datasource
        self._filter_order_spin: Optional[QtWidgets.QSpinBox] = None
        self._n_bootstrap_spin: Optional[QtWidgets.QSpinBox] = None
        self._baseline_start_none_cb: Optional[QtWidgets.QCheckBox] = None
        self._baseline_start_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._baseline_end_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._show_confidence_cb: Optional[QtWidgets.QCheckBox] = None
        self._line_width_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        self._nominal_auto_cb: Optional[QtWidgets.QCheckBox] = None
        self._nominal_spin: Optional[QtWidgets.QDoubleSpinBox] = None
        super().__init__(parent)


    def _get_panel_title(self) -> str:
        return "EEG GFP (band power)"


    def _build_content_widget(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Filter order:"))
        self._filter_order_spin = QtWidgets.QSpinBox()
        self._filter_order_spin.setRange(1, 16)
        self._filter_order_spin.setValue(int(self._ds._gfp_filter_order))
        self._filter_order_spin.valueChanged.connect(self._apply_all_to_datasource)
        row.addWidget(self._filter_order_spin)
        row.addStretch()
        layout.addLayout(row)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Bootstrap N:"))
        self._n_bootstrap_spin = QtWidgets.QSpinBox()
        self._n_bootstrap_spin.setRange(10, 10_000)
        self._n_bootstrap_spin.setSingleStep(10)
        self._n_bootstrap_spin.setValue(int(self._ds._gfp_n_bootstrap))
        self._n_bootstrap_spin.valueChanged.connect(self._apply_all_to_datasource)
        row2.addWidget(self._n_bootstrap_spin)
        row2.addStretch()
        layout.addLayout(row2)
        self._baseline_start_none_cb = QtWidgets.QCheckBox("Baseline start: use interval start (None)")
        bs_none = self._ds._gfp_baseline_start is None
        self._baseline_start_none_cb.setChecked(bs_none)
        self._baseline_start_none_cb.toggled.connect(self._on_baseline_start_mode_toggled)
        self._baseline_start_none_cb.toggled.connect(self._apply_all_to_datasource)
        layout.addWidget(self._baseline_start_none_cb)
        row_bs = QtWidgets.QHBoxLayout()
        row_bs.addWidget(QtWidgets.QLabel("Baseline start (s):"))
        self._baseline_start_spin = QtWidgets.QDoubleSpinBox()
        self._baseline_start_spin.setRange(-1.0e9, 1.0e9)
        self._baseline_start_spin.setDecimals(6)
        self._baseline_start_spin.setValue(float(self._ds._gfp_baseline_start) if self._ds._gfp_baseline_start is not None else 0.0)
        self._baseline_start_spin.valueChanged.connect(self._apply_all_to_datasource)
        row_bs.addWidget(self._baseline_start_spin)
        row_bs.addStretch()
        layout.addLayout(row_bs)
        row_be = QtWidgets.QHBoxLayout()
        row_be.addWidget(QtWidgets.QLabel("Baseline end (s):"))
        self._baseline_end_spin = QtWidgets.QDoubleSpinBox()
        self._baseline_end_spin.setRange(-1.0e9, 1.0e9)
        self._baseline_end_spin.setDecimals(6)
        self._baseline_end_spin.setValue(float(self._ds._gfp_baseline_end))
        self._baseline_end_spin.valueChanged.connect(self._apply_all_to_datasource)
        row_be.addWidget(self._baseline_end_spin)
        row_be.addStretch()
        layout.addLayout(row_be)
        self._on_baseline_start_mode_toggled(bs_none)
        self._show_confidence_cb = QtWidgets.QCheckBox("Show bootstrap confidence")
        self._show_confidence_cb.setChecked(bool(self._ds._gfp_show_confidence))
        self._show_confidence_cb.toggled.connect(self._apply_all_to_datasource)
        layout.addWidget(self._show_confidence_cb)
        row_lw = QtWidgets.QHBoxLayout()
        row_lw.addWidget(QtWidgets.QLabel("Line width:"))
        self._line_width_spin = QtWidgets.QDoubleSpinBox()
        self._line_width_spin.setRange(0.05, 20.0)
        self._line_width_spin.setDecimals(3)
        self._line_width_spin.setValue(float(self._ds._gfp_line_width))
        self._line_width_spin.valueChanged.connect(self._apply_all_to_datasource)
        row_lw.addWidget(self._line_width_spin)
        row_lw.addStretch()
        layout.addLayout(row_lw)
        self._nominal_auto_cb = QtWidgets.QCheckBox("Nominal sample rate: auto (from raw sfreq)")
        from pypho_timeline.rendering.datasources.specific.eeg import _first_sfreq_from_raw_datasets_dict
        inferred = _first_sfreq_from_raw_datasets_dict(self._ds.raw_datasets_dict)
        cur = self._ds._gfp_nominal_srate
        if cur is None:
            auto_nom = True
        elif inferred is None:
            auto_nom = False
        else:
            auto_nom = abs(float(cur) - float(inferred)) < 1e-3
        self._nominal_auto_cb.setChecked(auto_nom)
        self._nominal_auto_cb.toggled.connect(self._on_nominal_auto_toggled)
        self._nominal_auto_cb.toggled.connect(self._apply_all_to_datasource)
        layout.addWidget(self._nominal_auto_cb)
        row_nm = QtWidgets.QHBoxLayout()
        row_nm.addWidget(QtWidgets.QLabel("Nominal srate (Hz):"))
        self._nominal_spin = QtWidgets.QDoubleSpinBox()
        self._nominal_spin.setRange(1.0, 1.0e6)
        self._nominal_spin.setDecimals(2)
        self._nominal_spin.setValue(float(cur) if cur is not None and cur > 0 else (float(inferred) if inferred is not None else 250.0))
        self._nominal_spin.valueChanged.connect(self._apply_all_to_datasource)
        row_nm.addWidget(self._nominal_spin)
        row_nm.addStretch()
        layout.addLayout(row_nm)
        self._on_nominal_auto_toggled(self._nominal_auto_cb.isChecked())
        layout.addStretch()
        return root


    @pyqtExceptionPrintingSlot()
    def _on_baseline_start_mode_toggled(self, use_none: bool) -> None:
        if self._baseline_start_spin is not None:
            self._baseline_start_spin.setEnabled(not use_none)


    @pyqtExceptionPrintingSlot()
    def _on_nominal_auto_toggled(self, auto: bool) -> None:
        if self._nominal_spin is not None:
            self._nominal_spin.setEnabled(not auto)


    @pyqtExceptionPrintingSlot()
    def _apply_all_to_datasource(self) -> None:
        if self._filter_order_spin is None or self._n_bootstrap_spin is None or self._baseline_end_spin is None or self._show_confidence_cb is None or self._line_width_spin is None:
            return
        baseline_start = None if (self._baseline_start_none_cb is not None and self._baseline_start_none_cb.isChecked()) else (float(self._baseline_start_spin.value()) if self._baseline_start_spin is not None else None)
        nominal = None if (self._nominal_auto_cb is not None and self._nominal_auto_cb.isChecked()) else float(self._nominal_spin.value()) if self._nominal_spin is not None else None
        self._ds.set_gfp_display_params(int(self._filter_order_spin.value()), int(self._n_bootstrap_spin.value()), baseline_start, float(self._baseline_end_spin.value()), self._show_confidence_cb.isChecked(), float(self._line_width_spin.value()), nominal)
        self.gfpOptionsApplied.emit()
        self.optionsChanged.emit()


    def track_options_kind(self) -> Optional[str]:
        return TRACK_OPTIONS_KIND_LINE_POWER_GFP


    def dump_track_options_state(self) -> Optional[Dict[str, Any]]:
        auto_nom = self._nominal_auto_cb.isChecked() if self._nominal_auto_cb is not None else True
        return {"kind": TRACK_OPTIONS_KIND_LINE_POWER_GFP, "filter_order": int(self._ds._gfp_filter_order), "n_bootstrap": int(self._ds._gfp_n_bootstrap),
                "baseline_start": self._ds._gfp_baseline_start, "baseline_end": float(self._ds._gfp_baseline_end), "show_confidence": bool(self._ds._gfp_show_confidence),
                "line_width": float(self._ds._gfp_line_width), "nominal_srate_auto": auto_nom, "nominal_srate": (None if auto_nom else (float(self._nominal_spin.value()) if self._nominal_spin is not None else None))}


    def apply_track_options_state(self, data: Dict[str, Any]) -> None:
        if data.get("kind") != TRACK_OPTIONS_KIND_LINE_POWER_GFP:
            return
        fo = data.get("filter_order")
        nb = data.get("n_bootstrap")
        if fo is not None and self._filter_order_spin is not None:
            self._filter_order_spin.blockSignals(True)
            self._filter_order_spin.setValue(int(fo))
            self._filter_order_spin.blockSignals(False)
        if nb is not None and self._n_bootstrap_spin is not None:
            self._n_bootstrap_spin.blockSignals(True)
            self._n_bootstrap_spin.setValue(int(nb))
            self._n_bootstrap_spin.blockSignals(False)
        bs = data.get("baseline_start")
        if self._baseline_start_none_cb is not None and self._baseline_start_spin is not None:
            self._baseline_start_none_cb.blockSignals(True)
            self._baseline_start_spin.blockSignals(True)
            self._baseline_start_none_cb.setChecked(bs is None)
            if bs is not None:
                self._baseline_start_spin.setValue(float(bs))
            self._baseline_start_none_cb.blockSignals(False)
            self._baseline_start_spin.blockSignals(False)
            self._on_baseline_start_mode_toggled(self._baseline_start_none_cb.isChecked())
        be = data.get("baseline_end")
        if be is not None and self._baseline_end_spin is not None:
            self._baseline_end_spin.blockSignals(True)
            self._baseline_end_spin.setValue(float(be))
            self._baseline_end_spin.blockSignals(False)
        sc = data.get("show_confidence")
        if sc is not None and self._show_confidence_cb is not None:
            self._show_confidence_cb.blockSignals(True)
            self._show_confidence_cb.setChecked(bool(sc))
            self._show_confidence_cb.blockSignals(False)
        lw = data.get("line_width")
        if lw is not None and self._line_width_spin is not None:
            self._line_width_spin.blockSignals(True)
            self._line_width_spin.setValue(float(lw))
            self._line_width_spin.blockSignals(False)
        auto = data.get("nominal_srate_auto")
        ns = data.get("nominal_srate")
        if self._nominal_auto_cb is not None:
            self._nominal_auto_cb.blockSignals(True)
            if auto is not None:
                self._nominal_auto_cb.setChecked(bool(auto))
            elif ns is None:
                self._nominal_auto_cb.setChecked(True)
            else:
                self._nominal_auto_cb.setChecked(False)
            self._nominal_auto_cb.blockSignals(False)
            self._on_nominal_auto_toggled(self._nominal_auto_cb.isChecked())
        if ns is not None and self._nominal_spin is not None:
            self._nominal_spin.blockSignals(True)
            self._nominal_spin.setValue(float(ns))
            self._nominal_spin.blockSignals(False)
        self._apply_all_to_datasource()


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
    "EEGSpectrogramTrackOptionsPanel",
    "LinePowerGFPTrackOptionsPanel",
    "TrackOptionsPanelOwningMixin",
    "TRACK_OPTIONS_CONFIG_VERSION",
    "TRACK_OPTIONS_KIND_CHANNEL_VISIBILITY",
    "TRACK_OPTIONS_KIND_EEG_SPECTROGRAM",
    "TRACK_OPTIONS_KIND_LINE_POWER_GFP",
    "build_track_options_document",
    "apply_track_options_document",
]

