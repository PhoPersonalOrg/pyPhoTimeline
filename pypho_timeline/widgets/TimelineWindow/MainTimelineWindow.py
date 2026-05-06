# MainTimelineWindow.py
# Generated from c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.ui automatically by PhoPyQtClassGenerator VSCode Extension
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING, Union
from qtpy import QtWidgets, QtCore
from qtpy.uic import loadUi
from qtpy.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QMainWindow, QVBoxLayout

if TYPE_CHECKING:
    from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
    


## IMPORTS:
from pypho_timeline.widgets.log_widget import LogWidget, QtLogHandler
from pypho_timeline.utils.logging_util import get_rendering_logger
from pypho_timeline.utils.window_icon import ensure_timeline_application_window_icon, timeline_window_icon
from pypho_timeline.xdf_session_discovery import discover_xdf_files_for_timeline
from pypho_timeline.widgets.simple_timeline_widget import SimpleTimelineWidget, SimpleTimeWindow
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, IntervalProvidingTrackDatasource
import pypho_timeline.resources.icons.icons_rc  # noqa: F401


## Define the .ui file path
path = os.path.dirname(os.path.abspath(__file__))
uiFile = os.path.join(path, 'MainTimelineWindow.ui')

SESSION_JUMP_INTERVALS_TRACK_ID = 'EEG_Epoc X'

_logger = get_rendering_logger(__name__)


class MainTimelineWindow(QMainWindow):
    """ the main timeline application root window """

    def __init__(self, parent=None, show_immediately: bool = True, refresh_callback: Optional[Callable[[], None]] = None, builder: Optional[Any] = None):
        super().__init__(parent=parent) # Call the inherited classes __init__ method
        self._refresh_callback = refresh_callback
        self._timeline_builder = builder
        self._collapsed_dock_overflow_controller = None
        self.ui = loadUi(uiFile, self) # Load the .ui file
        self.initUI()
        if show_immediately:
            self.show() # Show the GUI


    @property
    def builder(self):
        """The builder property."""
        return self._timeline_builder


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
        if hasattr(self, "actionFit_All_Items"):
            self.actionFit_All_Items.triggered.connect(self._on_go_to_fit_all_items)
        if hasattr(self, "actionExportSingle_PDF_file"):
            self.actionExportSingle_PDF_file.triggered.connect(self._on_export_single_pdf_file)
        if hasattr(self, "actionseparate_PDF_per_track"):
            self.actionseparate_PDF_per_track.triggered.connect(self._on_export_separate_pdf_per_track)
        if hasattr(self, "actionAdd_Video_Track"):
            self.actionAdd_Video_Track.triggered.connect(self._on_add_video_track)
        if hasattr(self, "actionAdd_EEG_Spectrogram_Track"):
            self.actionAdd_EEG_Spectrogram_Track.triggered.connect(self._on_add_eeg_spectrogram_track)
        if hasattr(self, "actionAdd_Calendar_Navigator_Track"):
            self.actionAdd_Calendar_Navigator_Track.triggered.connect(self._on_add_calendar_navigator_track)
        if hasattr(self, "actionAdd_DataFrame_Table_Track"):
            self.actionAdd_DataFrame_Table_Track.triggered.connect(self._on_add_dataframe_table_track)
        if hasattr(self, "sessionJumpButton"):
            self.sessionJumpButton.clicked.connect(self._on_session_jump_clicked)
        self.sync_session_jump_controls()
        self._sync_add_track_actions_enabled()
        self.setWindowIcon(timeline_window_icon())
        ensure_timeline_application_window_icon()
        if hasattr(self, "collapsedDockOverflowStrip"):
            self.collapsedDockOverflowStrip.setVisible(False)


    @classmethod
    def init_with_timeline(cls, timeline: SimpleTimelineWidget, builder: Optional[Any] = None,
            window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800),
            **kwargs,
        ) -> "MainTimelineWindow":
        """ 

        """
        # Create main window (do not show until timeline is added and configured)
        main_window = cls(show_immediately=False, builder=builder)
        # Create the timeline widget with reference datetime, parented to main window content area
        # timeline = SimpleTimelineWidget(total_start_time=total_start_time, total_end_time=total_end_time, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, reference_datetime=reference_datetime, parent=main_window.contentWidget)
        main_window.contentWidget.layout().addWidget(timeline)
        # Add tracks to the timeline
        datasources = kwargs.pop('datasources', None)
        if datasources is not None:
            timeline.add_tracks_from_datasources(datasources=datasources, **kwargs) # use_absolute_datetime_track_mode=use_absolute_datetime_track_mode, 

        main_window.sync_session_jump_controls()



        if builder is not None:
            added_timeline_idx: int = len(builder.current_main_windows)
            assert len(builder.current_timeline_widgets) == len(builder.current_main_windows), f"len(builder.current_timeline_widgets): {len(builder.current_timeline_widgets)} != len(builder.current_main_windows): {len(builder.current_main_windows)}.\n\t proposed_added_timeline_idx: {added_timeline_idx}"
            print(f'added_timeline_idx: {added_timeline_idx}')
            _logger.info(f"\nadded_timeline_idx: {added_timeline_idx}")

            builder.current_main_windows.append(main_window)
            builder.current_timeline_widgets.append(timeline)
        else:
            raise ValueError(f'builder is None!')


        # Configure and show main window
        main_window.setWindowTitle(window_title or "pyPhoTimeline")
        main_window.resize(window_size[0], window_size[1])
        main_window.show()

        # ## Add the calendar widget
        # if enable_calendar_widget_track:
        #     a_cal_nav = timeline.add_calendar_navigator()


        if builder is not None:
            builder._embed_log_widget_in_timeline(timeline)

        main_window.attach_collapsed_dock_overflow(timeline.ui.dynamic_docked_widget_container)

        # ## add the table widget:
        # if enable_log_table_widget:
        #     if "LOG_TextLogger" in timeline.track_datasources:
        #         table_widget = timeline.add_dataframe_table_track("Text Log", timeline.track_datasources["LOG_TextLogger"].df) # timeline.add_dataframe_table_track()
        
        # _logger.info("\nTimeline widget created with tracks:")
        # for ds in datasources:
        #     _logger.info(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        # _logger.info("\nScroll on the timeline to see loaded intervals for each stream.")
        # _logger.info("Close the window to exit.\n")

        ## hide the extra/redundant xaxis labels
        # timeline.hide_extra_xaxis_labels_and_axes()

        return main_window


    @classmethod
    def init_creating_new_timeline(cls, datasources: List[TrackDatasource], window_duration: Optional[float] = None, window_start_time: Optional[float] = None,
                window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), reference_datetime: Optional[datetime] = None,
                # use_absolute_datetime_track_mode: bool = True,
                enable_calendar_widget_track: bool = False, enable_log_table_widget: bool = False,
                builder: Optional[Any] = None, **kwargs) -> "MainTimelineWindow":
        """ 

        """
        # Create the timeline widget with reference datetime, parented to main window content area
        # timeline: SimpleTimelineWidget = SimpleTimelineWidget(total_start_time=total_start_time, total_end_time=total_end_time, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, reference_datetime=reference_datetime) # , parent=main_window.contentWidget

        # Create main window (do not show until timeline is added and configured)
        main_window = cls(show_immediately=False, builder=builder)
        # Create the timeline widget with reference datetime, parented to main window content area
        timeline: SimpleTimelineWidget = SimpleTimelineWidget(total_start_time=total_start_time, total_end_time=total_end_time, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, reference_datetime=reference_datetime, parent=main_window.contentWidget)
        main_window.contentWidget.layout().addWidget(timeline)
        # Add tracks to the timeline
        timeline.add_tracks_from_datasources(datasources=datasources, use_absolute_datetime_track_mode=use_absolute_datetime_track_mode, **kwargs)
        self._sync_main_window_session_jump_controls(main_window=main_window)

        added_timeline_idx: int = len(self.current_main_windows)
        assert len(self.current_timeline_widgets) == len(self.current_main_windows), f"len(self.current_timeline_widgets): {len(self.current_timeline_widgets)} != len(self.current_main_windows): {len(self.current_main_windows)}.\n\t proposed_added_timeline_idx: {added_timeline_idx}"
        print(f'added_timeline_idx: {added_timeline_idx}')
        logger.info(f"\nadded_timeline_idx: {added_timeline_idx}")


        self.current_main_windows.append(main_window)
        self.current_timeline_widgets.append(timeline)
        # Configure and show main window
        main_window.setWindowTitle(window_title or "pyPhoTimeline")
        main_window.resize(window_size[0], window_size[1])
        main_window.show()

        ## Add the calendar widget
        if enable_calendar_widget_track:
            a_cal_nav = timeline.add_calendar_navigator()

        self._embed_log_widget_in_timeline(timeline)
        main_window.attach_collapsed_dock_overflow(timeline.ui.dynamic_docked_widget_container)

        ## add the table widget:
        if enable_log_table_widget:
            if "LOG_TextLogger" in timeline.track_datasources:
                table_widget = timeline.add_dataframe_table_track("Text Log", timeline.track_datasources["LOG_TextLogger"].df) # timeline.add_dataframe_table_track()
        
        logger.info("\nTimeline widget created with tracks:")
        for ds in datasources:
            logger.info(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        logger.info("\nScroll on the timeline to see loaded intervals for each stream.")
        logger.info("Close the window to exit.\n")

        ## hide the extra/redundant xaxis labels
        timeline.hide_extra_xaxis_labels_and_axes()
        return main_window




    def attach_collapsed_dock_overflow(self, nested_dock_area: "NestedDockAreaWidget") -> None:
        from pypho_timeline.docking.collapsed_dock_overflow_controller import CollapsedDockOverflowController
        if not hasattr(self, "collapsedDockOverflowContents") or not hasattr(self, "collapsedDockOverflowStrip"):
            return
        if self._collapsed_dock_overflow_controller is None:
            self._collapsed_dock_overflow_controller = CollapsedDockOverflowController(self.collapsedDockOverflowContents, strip_widget=self.collapsedDockOverflowStrip, parent=self)
        self._collapsed_dock_overflow_controller.bind_to_nested_dock_area(nested_dock_area)


    def sync_session_jump_controls(self):
        self._sync_add_track_actions_enabled()
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


    def _on_go_to_fit_all_items(self):
        tw = self.timeline_widget
        if tw is None:
            return
        if hasattr(tw, "go_to_fit_all_items"):
            tw.go_to_fit_all_items()




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


    def _on_export_single_pdf_file(self):
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "export_all_tracks_as_single_pdf"):
            return
        try:
            exported_path = tw.export_all_tracks_as_single_pdf()
        except Exception as e:
            _logger.warning("export single pdf file failed: %s", e)
            QMessageBox.warning(self, "Export single PDF file", str(e))
            return
        if exported_path is None:
            return
        QMessageBox.information(self, "Export single PDF file", f"Exported stacked track PDF to:\n{exported_path}")


    def _on_export_separate_pdf_per_track(self):
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "export_all_tracks_as_pdf"):
            return
        try:
            exported_paths = tw.export_all_tracks_as_pdf()
        except Exception as e:
            _logger.warning("export separate pdf per track failed: %s", e)
            QMessageBox.warning(self, "Export separate PDF per track", str(e))
            return
        if not exported_paths:
            return
        first_parent = Path(exported_paths[0]).parent
        QMessageBox.information(self, "Export separate PDF per track", f"Exported {len(exported_paths)} track PDF file(s) to:\n{first_parent}")


    def _sync_add_track_actions_enabled(self) -> None:
        """Enable/disable Add Track actions based on the current timeline state."""
        tw = self.timeline_widget
        has_timeline = tw is not None
        has_eeg_source = has_timeline and len(self._candidate_eeg_source_track_names()) > 0 and self._timeline_builder is not None
        has_table_candidate = has_timeline and len(self._candidate_dataframe_table_track_names()) > 0
        if hasattr(self, "actionAdd_Video_Track"):
            self.actionAdd_Video_Track.setEnabled(has_timeline)
        if hasattr(self, "actionAdd_EEG_Spectrogram_Track"):
            self.actionAdd_EEG_Spectrogram_Track.setEnabled(has_eeg_source)
        if hasattr(self, "actionAdd_Calendar_Navigator_Track"):
            self.actionAdd_Calendar_Navigator_Track.setEnabled(has_timeline)
        if hasattr(self, "actionAdd_DataFrame_Table_Track"):
            self.actionAdd_DataFrame_Table_Track.setEnabled(has_table_candidate)


    def _candidate_eeg_source_track_names(self) -> List[str]:
        """Names of EEG source datasources eligible for spectrogram computation (have raws, not themselves spectrograms)."""
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "track_datasources"):
            return []
        try:
            from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource, EEGSpectrogramTrackDatasource
        except Exception:
            return []
        names: List[str] = []
        for name, ds in tw.track_datasources.items():
            if ds is None:
                continue
            if EEGSpectrogramTrackDatasource is not None and isinstance(ds, EEGSpectrogramTrackDatasource):
                continue
            if not isinstance(ds, EEGTrackDatasource):
                continue
            if not getattr(ds, "raw_datasets_dict", None):
                continue
            names.append(name)
        return names


    def _candidate_dataframe_table_track_names(self) -> List[str]:
        """Names of tracks whose datasource exposes a non-empty ``detailed_df`` for table display."""
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "track_datasources"):
            return []
        names: List[str] = []
        for name, ds in tw.track_datasources.items():
            if ds is None:
                continue
            df = getattr(ds, "detailed_df", None)
            if df is None:
                continue
            try:
                if hasattr(df, "empty") and df.empty:
                    continue
            except Exception:
                pass
            names.append(name)
        return names


    DEFAULT_VIDEO_DISCOVERY_DIRS: Tuple[Path, ...] = (Path("M:/ScreenRecordings/EyeTrackerVR_Recordings"), Path("M:/ScreenRecordings/REC_continuous_video_recorder"))
    DEFAULT_VIDEO_MAX_NUM_RECENT: int = 25


    def _resolve_video_discovery_dirs(self) -> List[Path]:
        """Builder-configured ``video_discovery_dirs`` if any, otherwise the notebook defaults."""
        if self._timeline_builder is not None:
            rc = getattr(self._timeline_builder, "_refresh_config", None)
            if rc:
                configured = rc.get("video_discovery_dirs", []) or []
                resolved = [Path(p) for p in configured]
                if resolved:
                    return resolved
        return [Path(p) for p in self.DEFAULT_VIDEO_DISCOVERY_DIRS]


    def _on_add_video_track(self):
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "add_video_track"):
            QMessageBox.warning(self, "Add Video Track", "No active timeline to add a track to.")
            return
        try:
            from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
            from phopylslhelper.file_metadata_caching.manager import BaseFileMetadataManager
            from phopylslhelper.file_metadata_caching.video_metadata import VideoMetadataParser
        except Exception as e:
            _logger.warning("add video track: video deps unavailable: %s", e)
            QMessageBox.warning(self, "Add Video Track", f"Video support is unavailable:\n{e}")
            return
        discovery_dirs = self._resolve_video_discovery_dirs()
        existing_dirs = [d for d in discovery_dirs if d.exists() and d.is_dir()]
        if not existing_dirs:
            missing = "\n".join(str(d) for d in discovery_dirs)
            QMessageBox.information(self, "Add Video Track", f"None of the configured video discovery directories exist:\n{missing}")
            return
        try:
            video_manager = BaseFileMetadataManager(parse_folders=existing_dirs, parsers={'video': VideoMetadataParser})
            recent_videos = video_manager.get_most_recent_video_paths(max_num_videos=self.DEFAULT_VIDEO_MAX_NUM_RECENT)
        except Exception as e:
            _logger.warning("add video track: video discovery failed: %s", e)
            QMessageBox.warning(self, "Add Video Track", f"Video discovery failed:\n{e}")
            return
        if not recent_videos:
            dirs_str = "\n".join(str(d) for d in existing_dirs)
            QMessageBox.information(self, "Add Video Track", f"No videos found under:\n{dirs_str}")
            return
        track_name = "RecentVideosTrack"
        suffix = 1
        while track_name in getattr(tw, "track_datasources", {}):
            suffix += 1
            track_name = f"RecentVideosTrack_{suffix}"
        video_paths: List[Union[Path, str]] = [Path(p) for p in recent_videos]
        try:
            video_ds = VideoTrackDatasource(video_paths=video_paths, custom_datasource_name=track_name)
            tw.add_video_track(track_name=track_name, video_datasource=video_ds, enable_time_crosshair=True)
        except Exception as e:
            _logger.warning("add video track failed: %s", e)
            QMessageBox.warning(self, "Add Video Track", str(e))
            return
        self._sync_add_track_actions_enabled()


    def _on_add_eeg_spectrogram_track(self):
        tw = self.timeline_widget
        if tw is None:
            QMessageBox.warning(self, "Add EEG Spectrogram", "No active timeline to add a track to.")
            return
        candidate_names = self._candidate_eeg_source_track_names()
        if not candidate_names:
            QMessageBox.information(self, "Add EEG Spectrogram", "No EEG source datasources with raws are loaded.")
            return
        if self._timeline_builder is None:
            QMessageBox.warning(self, "Add EEG Spectrogram", "Timeline builder is required to add spectrogram tracks.")
            return
        from pypho_timeline.widgets.TimelineWindow.add_track_dialogs import AddEEGSpectrogramDialog
        from qtpy.QtWidgets import QDialog
        dialog = AddEEGSpectrogramDialog(eeg_track_names=candidate_names, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        eeg_track_name = dialog.selected_eeg_track_name
        if not eeg_track_name:
            return
        groups = dialog.selected_groups
        eeg_ds = tw.track_datasources.get(eeg_track_name) if hasattr(tw, "track_datasources") else None
        if eeg_ds is None:
            QMessageBox.warning(self, "Add EEG Spectrogram", f"Could not resolve EEG datasource '{eeg_track_name}'.")
            return
        try:
            created = eeg_ds.add_spectrogram_tracks_for_channel_groups(spectrogram_channel_groups=groups, timeline=tw, timeline_builder=self._timeline_builder)
        except Exception as e:
            _logger.warning("add eeg spectrogram track failed: %s", e)
            QMessageBox.warning(self, "Add EEG Spectrogram", str(e))
            return
        if not created:
            QMessageBox.information(self, "Add EEG Spectrogram", "No new spectrogram tracks were added (they may already exist).")
        self._sync_add_track_actions_enabled()


    def _on_add_calendar_navigator_track(self):
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "add_calendar_navigator"):
            QMessageBox.warning(self, "Add Calendar Navigator", "No active timeline to add a track to.")
            return
        if hasattr(tw, "ui") and getattr(tw.ui, "calendar", None) is not None:
            QMessageBox.information(self, "Add Calendar Navigator", "A calendar navigator is already attached to this timeline.")
            return
        try:
            tw.add_calendar_navigator()
        except Exception as e:
            _logger.warning("add calendar navigator failed: %s", e)
            QMessageBox.warning(self, "Add Calendar Navigator", str(e))


    def _on_add_dataframe_table_track(self):
        tw = self.timeline_widget
        if tw is None or not hasattr(tw, "add_dataframe_table_track"):
            QMessageBox.warning(self, "Add DataFrame Table", "No active timeline to add a track to.")
            return
        candidate_names = self._candidate_dataframe_table_track_names()
        if not candidate_names:
            QMessageBox.information(self, "Add DataFrame Table", "No tracks with a detailed DataFrame are available.")
            return
        track_name, ok = QInputDialog.getItem(self, "Add DataFrame Table", "Source track:", candidate_names, 0, False)
        if not ok or not track_name:
            return
        ds = tw.track_datasources.get(track_name) if hasattr(tw, "track_datasources") else None
        if ds is None:
            QMessageBox.warning(self, "Add DataFrame Table", f"Could not resolve source track '{track_name}'.")
            return
        df = getattr(ds, "detailed_df", None)
        if df is None:
            QMessageBox.warning(self, "Add DataFrame Table", f"Track '{track_name}' has no detailed DataFrame.")
            return
        table_track_name = f"{track_name}_table"
        if hasattr(tw, "ui") and hasattr(tw.ui, "dynamic_docked_widget_container"):
            existing = tw.ui.dynamic_docked_widget_container.find_display_dock(table_track_name)
            if existing is not None:
                existing.show()
                existing.raise_()
                return
        try:
            tw.add_dataframe_table_track(track_name=table_track_name, dataframe=df, time_column='t', dockSize=(400, 200))
        except Exception as e:
            _logger.warning("add dataframe table track failed: %s", e)
            QMessageBox.warning(self, "Add DataFrame Table", str(e))


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
