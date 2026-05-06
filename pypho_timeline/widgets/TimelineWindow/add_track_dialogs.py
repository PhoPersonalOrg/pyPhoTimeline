"""Dialogs used by the "Add Track" menu in :class:`MainTimelineWindow`.

Currently provides :class:`AddEEGSpectrogramDialog`, which lets the user pick an
EEG source stream and one or more channel groups for spectrogram computation.
"""
from __future__ import annotations

from typing import List, Optional

from qtpy import QtCore, QtWidgets


class AddEEGSpectrogramDialog(QtWidgets.QDialog):
    """Pick an EEG track and channel group(s) to compute spectrogram tracks for.

    The "All channels averaged" option maps to passing ``None`` to
    ``EEGTrackDatasource.add_spectrogram_tracks_for_channel_groups``, which
    yields a single spectrogram track averaging every channel.
    """

    _ALL_CHANNELS_AVERAGED_LABEL = "All channels averaged (single track)"


    def __init__(self, eeg_track_names: List[str], default_groups: Optional[List["SpectrogramChannelGroupConfig"]] = None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent=parent)
        from pypho_timeline.rendering.datasources.specific.eeg import EMOTIV_EPOC_X_SPECTROGRAM_GROUPS
        self._available_groups = list(default_groups) if default_groups is not None else list(EMOTIV_EPOC_X_SPECTROGRAM_GROUPS)
        self.setWindowTitle("Add EEG Spectrogram Track")
        self.setModal(True)
        self.resize(360, 320)
        self._build_ui(eeg_track_names)


    def _build_ui(self, eeg_track_names: List[str]) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        stream_label = QtWidgets.QLabel("EEG source stream:", self)
        layout.addWidget(stream_label)
        self._stream_combo = QtWidgets.QComboBox(self)
        for name in eeg_track_names:
            self._stream_combo.addItem(name)
        layout.addWidget(self._stream_combo)
        groups_label = QtWidgets.QLabel("Channel group(s) to add:", self)
        layout.addWidget(groups_label)
        self._groups_list = QtWidgets.QListWidget(self)
        self._groups_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for group_cfg in self._available_groups:
            item = QtWidgets.QListWidgetItem(f"{group_cfg.name}  ({len(group_cfg.channels)} ch)", self._groups_list)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, group_cfg)
        all_item = QtWidgets.QListWidgetItem(self._ALL_CHANNELS_AVERAGED_LABEL, self._groups_list)
        all_item.setFlags(all_item.flags() | QtCore.Qt.ItemIsUserCheckable)
        all_item.setCheckState(QtCore.Qt.Unchecked)
        all_item.setData(QtCore.Qt.UserRole, None)
        layout.addWidget(self._groups_list)
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


    @property
    def selected_eeg_track_name(self) -> Optional[str]:
        text = self._stream_combo.currentText()
        return text if text else None


    @property
    def selected_groups(self) -> Optional[List["SpectrogramChannelGroupConfig"]]:
        """List of selected channel-group configs, or ``None`` if user picked "All channels averaged"."""
        all_item = self._groups_list.item(self._groups_list.count() - 1)
        if all_item is not None and all_item.checkState() == QtCore.Qt.Checked:
            return None
        selected: List = []
        for i in range(self._groups_list.count() - 1):
            item = self._groups_list.item(i)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                cfg = item.data(QtCore.Qt.UserRole)
                if cfg is not None:
                    selected.append(cfg)
        return selected
