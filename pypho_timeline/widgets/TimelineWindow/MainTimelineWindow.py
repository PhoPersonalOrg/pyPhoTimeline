# MainTimelineWindow.py
# Generated from c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.ui automatically by PhoPyQtClassGenerator VSCode Extension
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Union, Any, TYPE_CHECKING
from qtpy import QtWidgets, QtCore
from qtpy.uic import loadUi
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox, QMainWindow, QVBoxLayout

if TYPE_CHECKING:
    from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget

## IMPORTS:
from pypho_timeline.widgets.log_widget import LogWidget, QtLogHandler
from pypho_timeline.utils.logging_util import get_rendering_logger
from pypho_timeline.utils.window_icon import ensure_timeline_application_window_icon, timeline_window_icon
from pypho_timeline.xdf_session_discovery import discover_xdf_files_for_timeline


## Define the .ui file path
path = os.path.dirname(os.path.abspath(__file__))
uiFile = os.path.join(path, 'MainTimelineWindow.ui')

SESSION_JUMP_INTERVALS_TRACK_ID = 'EEG_Epoc X'

_logger = get_rendering_logger(__name__)


class MainTimelineWindow(QMainWindow):
    def __init__(self, parent=None, show_immediately: bool = True, refresh_callback: Optional[Callable[[], None]] = None, builder: Optional[Any] = None):
        super().__init__(parent=parent) # Call the inherited classes __init__ method
        self._refresh_callback = refresh_callback
        self._timeline_builder = builder
        self._collapsed_dock_overflow_controller = None
        self.ui = loadUi(uiFile, self) # Load the .ui file
        self.initUI()
        if show_immediately:
            self.show() # Show the GUI

    def initUI(self):
        self.statusBar().hide()
        content_layout = QVBoxLayout(self.contentWidget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.contentWidget.setLayout(content_layout)
        self._log_widget = LogWidget(parent=self.logPanel)
        self.logPanel.layout().addWidget(self._log_widget)
        self.logPanel.setVisible(False)
        self.logToggleButton.setChecked(False)
        self.logToggleButton.setText("Show Log")
        self.logToggleButton.toggled.connect(self._on_log_toggle)
        if hasattr(self, "refreshFilesButton"):
            self.refreshFilesButton.clicked.connect(self._on_refresh_files_clicked)
            self.refreshFilesButton.setEnabled((self._refresh_callback is not None) or (self._timeline_builder is not None))
        _open_recording_enabled = (self._timeline_builder is not None) and hasattr(self._timeline_builder, "replace_timeline_from_xdf_paths")
        if hasattr(self, "actionOpen_Recording_File"):
            self.actionOpen_Recording_File.triggered.connect(self._on_open_recording_file)
            self.actionOpen_Recording_File.setEnabled(_open_recording_enabled)
        if hasattr(self, "actionOpen_Recording_Directory"):
            self.actionOpen_Recording_Directory.triggered.connect(self._on_open_recording_directory)
            self.actionOpen_Recording_Directory.setEnabled(_open_recording_enabled)
        _log_handler = QtLogHandler(parent=self)
        _log_handler.log_record_received.connect(self._log_widget.append_log)
        get_rendering_logger(__name__).addHandler(_log_handler)
        self._qt_log_handler = _log_handler
        if hasattr(self, "actionGoToEarliest"):
            self.actionGoToEarliest.triggered.connect(self._on_go_to_earliest)
        if hasattr(self, "actionGoToPrev"):
            self.actionGoToPrev.triggered.connect(self._on_go_to_prev)
        if hasattr(self, "actionGoToNext"):
            self.actionGoToNext.triggered.connect(self._on_go_to_next)
        if hasattr(self, "actionGoToLatest"):
            self.actionGoToLatest.triggered.connect(self._on_go_to_latest)
        if hasattr(self, "sessionJumpButton"):
            self.sessionJumpButton.clicked.connect(self._on_session_jump_clicked)
        self.sync_session_jump_controls()
        self.setWindowIcon(timeline_window_icon())
        ensure_timeline_application_window_icon()
        if hasattr(self, "collapsedDockOverflowStrip"):
            self.collapsedDockOverflowStrip.setVisible(False)


    def attach_collapsed_dock_overflow(self, nested_dock_area: "NestedDockAreaWidget") -> None:
        from pypho_timeline.docking.collapsed_dock_overflow_controller import CollapsedDockOverflowController
        if not hasattr(self, "collapsedDockOverflowContents") or not hasattr(self, "collapsedDockOverflowStrip"):
            return
        if self._collapsed_dock_overflow_controller is None:
            self._collapsed_dock_overflow_controller = CollapsedDockOverflowController(self.collapsedDockOverflowContents, strip_widget=self.collapsedDockOverflowStrip, parent=self)
        self._collapsed_dock_overflow_controller.bind_to_nested_dock_area(nested_dock_area)


    def sync_session_jump_controls(self):
        if not hasattr(self, "sessionJumpSpinBox") or not hasattr(self, "sessionJumpButton"):
            return
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "get_track_tuple"):
            self.sessionJumpSpinBox.setMaximum(0)
            self.sessionJumpSpinBox.setValue(0)
            self.sessionJumpButton.setEnabled(False)
            return
        _, _, ds = tw.get_track_tuple(SESSION_JUMP_INTERVALS_TRACK_ID)
        if ds is None or not hasattr(ds, "get_overview_intervals"):
            self.sessionJumpSpinBox.setMaximum(0)
            self.sessionJumpSpinBox.setValue(0)
            self.sessionJumpButton.setEnabled(False)
            return
        try:
            ov = ds.get_overview_intervals()
            n = len(ov)
        except Exception as e:
            _logger.warning("session jump: could not read overview intervals: %s", e)
            self.sessionJumpSpinBox.setMaximum(0)
            self.sessionJumpSpinBox.setValue(0)
            self.sessionJumpButton.setEnabled(False)
            return
        if n == 0:
            self.sessionJumpSpinBox.setMaximum(0)
            self.sessionJumpSpinBox.setValue(0)
            self.sessionJumpButton.setEnabled(False)
            return
        self.sessionJumpSpinBox.setMaximum(n - 1)
        if self.sessionJumpSpinBox.value() > n - 1:
            self.sessionJumpSpinBox.setValue(n - 1)
        self.sessionJumpButton.setEnabled(True)


    def _on_session_jump_clicked(self):
        self.sync_session_jump_controls()
        if not hasattr(self, "sessionJumpButton") or not self.sessionJumpButton.isEnabled():
            return
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "go_to_specific_interval"):
            return
        try:
            tw.go_to_specific_interval(self.sessionJumpSpinBox.value(), specific_intervals_ds_identifier=SESSION_JUMP_INTERVALS_TRACK_ID)
        except Exception as e:
            _logger.warning("session jump failed: %s", e)


    def _on_go_to_earliest(self):
        tw = self.timeline_widget
        if tw is None:
            return
        if hasattr(tw, "go_to_earliest_window"):
            tw.go_to_earliest_window()


    def _on_go_to_prev(self):
        tw = self.timeline_widget
        if tw is None:
            return
        if hasattr(tw, "jump_to_previous_interval"):
            tw.jump_to_previous_interval()


    def _on_go_to_next(self):
        tw = self.timeline_widget
        if tw is None:
            return
        if hasattr(tw, "jump_to_next_interval"):
            tw.jump_to_next_interval()


    def _on_go_to_latest(self):
        tw = self.timeline_widget
        if tw is None:
            return
        if hasattr(tw, "go_to_latest_window"):
            tw.go_to_latest_window()


    def _on_log_toggle(self, checked: bool):
        self.logPanel.setVisible(checked)
        self.logToggleButton.setText("Hide Log" if checked else "Show Log")


    def _on_refresh_files_clicked(self):
        if self._refresh_callback is not None:
            self._refresh_callback()
            return
        if self._timeline_builder is not None and hasattr(self._timeline_builder, "refresh_from_directories"):
            self._timeline_builder.refresh_from_directories()


    def _on_open_recording_file(self):
        if self._timeline_builder is None or not hasattr(self._timeline_builder, "replace_timeline_from_xdf_paths"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open recording file", "", "XDF recordings (*.xdf);;All files (*.*)")
        if not path:
            return
        try:
            loaded = self._timeline_builder.replace_timeline_from_xdf_paths([Path(path)])
        except Exception as e:
            _logger.warning("open recording file failed: %s", e)
            QMessageBox.warning(self, "Open recording file", str(e))
            return
        if loaded is None:
            QMessageBox.information(self, "Open recording file", "No streams could be loaded from the selected file.")


    def _on_open_recording_directory(self):
        if self._timeline_builder is None or not hasattr(self._timeline_builder, "replace_timeline_from_xdf_paths"):
            return
        directory = QFileDialog.getExistingDirectory(self, "Open recording directory")
        if not directory:
            return
        dir_path = Path(directory)
        n_recent = None
        if self._timeline_builder._refresh_config is not None:
            n_recent = self._timeline_builder._refresh_config.get("n_most_recent", None)
        try:
            discovered = discover_xdf_files_for_timeline(xdf_discovery_dirs=[dir_path], n_most_recent=n_recent)
        except Exception as e:
            _logger.warning("open recording directory: discovery failed: %s", e)
            QMessageBox.warning(self, "Open recording directory", str(e))
            return
        if not discovered.xdf_paths:
            QMessageBox.information(self, "Open recording directory", f"No .xdf files found under:\n{dir_path}")
            return
        try:
            loaded = self._timeline_builder.replace_timeline_from_xdf_paths(discovered.xdf_paths, xdf_discovery_dirs_for_refresh=[dir_path])
        except Exception as e:
            _logger.warning("open recording directory failed: %s", e)
            QMessageBox.warning(self, "Open recording directory", str(e))
            return
        if loaded is None:
            QMessageBox.information(self, "Open recording directory", "No streams could be loaded from the discovered .xdf files (check stream filters or file contents).")


    @property
    def timeline_widget(self):
        layout = self.contentWidget.layout()
        if layout is not None and layout.count() > 0:
            item = layout.itemAt(0)
            if item is not None and item.widget() is not None:
                return item.widget()
        return None


## Start Qt event loop
if __name__ == '__main__':
    app = QApplication([])
    widget = MainTimelineWindow()
    widget.show()
    sys.exit(app.exec() if hasattr(app, "exec") else app.exec_())
