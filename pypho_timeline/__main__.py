"""
Example usage of pyPhoTimeline library.

This demonstrates how to create a timeline with docked tracks that can display
time-synchronized data.
"""

from pathlib import Path
from re import S
import sys
import numpy as np
import pandas as pd
from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource, VideoTrackDatasource
from pypho_timeline.rendering.detail_renderers import MotionPlotDetailRenderer, VideoThumbnailDetailRenderer, GenericPlotDetailRenderer
from pypho_timeline.rendering.mixins.track_rendering_mixin import TrackRenderingMixin
from pypho_timeline.utils.logging_util import configure_logging

from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots

from pypho_timeline.widgets import SimpleTimelineWidget, perform_process_all_streams, modality_channels_dict, modality_sfreq_dict
from pypho_timeline.timeline_builder import TimelineBuilder


# ==================================================================================================================================================================================================================================================================================== #
# Testing Functions                                                                                                                                                                                                                                                                    #
# ==================================================================================================================================================================================================================================================================================== #

def main():
    """Main function demonstrating pyPhoTimeline usage."""
    print("=" * 60)
    print("pyPhoTimeline Example")
    print("=" * 60)
    
    # Configure logging for all pypho_timeline components (outputs to both stdout and file)
    import logging
    from pathlib import Path
    log_file = Path("timeline_rendering.log")
    configure_logging(
        log_level=logging.DEBUG,
        log_file=log_file,
        log_to_console=True,
        log_to_file=True
    )
    print(f"Logging configured for all pypho_timeline modules - output to console and {log_file}")
    
    # Create Qt application
    app = pg.mkQApp("pyPhoTimelineExample")
    
    # Create the timeline widget
    timeline = SimpleTimelineWidget(
        total_start_time=0.0,
        total_end_time=100.0,
        window_duration=15.0,
        window_start_time=30.0
    )
    
    # Set window properties
    timeline.setWindowTitle("pyPhoTimeline Example - Timeline with Docked Tracks")
    timeline.resize(800, 600)
    timeline.show()
    
    # Demonstrate programmatic window scrolling after a delay
    def scroll_demo():
        """Demonstrate scrolling the window."""
        print("\nDemonstrating window scrolling...")
        # Scroll forward
        timeline.simulate_window_scroll(40.0)
        QtCore.QTimer.singleShot(2000, lambda: timeline.simulate_window_scroll(50.0))
        QtCore.QTimer.singleShot(4000, lambda: timeline.simulate_window_scroll(60.0))
    
    # Start the scroll demo after 1 second
    QtCore.QTimer.singleShot(1000, scroll_demo)
    
    print("\nTimeline widget created with 6 example tracks:")
    print("  1. Overview track (NO_SYNC) - shows full time range")
    print("  2. Window track (TO_WINDOW) - syncs with active window")
    print("  3. Global track (TO_GLOBAL_DATA) - one-time sync to global range")
    print("  4. Intervals track (TO_GLOBAL_DATA) - displays time intervals as colored rectangles")
    print("  5. Position track (TO_GLOBAL_DATA) - async detail loading with position plots")
    print("  6. Video track (TO_GLOBAL_DATA) - async detail loading with video thumbnails")
    print("\nThe window will automatically scroll to demonstrate synchronization.")
    print("Scroll the position and video tracks to see detail data load asynchronously.")
    print("Hover over the interval rectangles to see tooltips.")
    print("Close the window to exit.\n")
    
    # Run the application
    sys.exit(app.exec_())




def main_all_modalities_from_xdf_file_example(xdf_file_path: Path):
    """Main function demonstrating pyPhoTimeline usage with all EEG modalities from an XDF file."""
    builder = TimelineBuilder()
    return builder.build_from_xdf_file(xdf_file_path)

    
    
def add_video_track(self, track_name: str, video_datasource: VideoTrackDatasource, dockSize: Tuple[int, int] = (500, 80), sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA):
        """Add a video track to the timeline.
        
        This is a convenience method that creates a plot widget and adds the video track.
        
        Args:
            track_name: Unique name for this video track
            video_datasource: VideoTrackDatasource instance
            dockSize: Size of the dock widget (width, height). Default: (500, 80)
            sync_mode: Synchronization mode for the plot. Default: TO_GLOBAL_DATA
            
        Returns:
            Tuple of (widget, root_graphics, plot_item, dock) from add_new_embedded_pyqtgraph_render_plot_widget
        """
        # Create plot widget
        video_widget, root_graphics, plot_item, dock = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name=track_name,
            dockSize=dockSize,
            dockAddLocationOpts=['bottom'],
            sync_mode=sync_mode
        )
        
        # Get time range from datasource
        t_start, t_end = video_datasource.total_df_start_end_times
        if t_start == t_end:
            # Default range if no data
            t_start = self.total_data_start_time
            t_end = self.total_data_end_time
        
        # Set plot ranges (convert to datetime then Unix timestamp if reference available)
        if hasattr(self, 'reference_datetime') and self.reference_datetime is not None:
            from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp
            dt_start = float_to_datetime(t_start, self.reference_datetime)
            dt_end = float_to_datetime(t_end, self.reference_datetime)
            # Convert datetime to Unix timestamp for PyQtGraph (DateAxisItem expects timestamps but displays as dates)
            unix_start = datetime_to_unix_timestamp(dt_start)
            unix_end = datetime_to_unix_timestamp(dt_end)
            plot_item.setXRange(unix_start, unix_end, padding=0)
            plot_item.setLabel('bottom', 'Time')
        else:
            plot_item.setXRange(t_start, t_end, padding=0)
            plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setYRange(0, 60, padding=0)
        plot_item.setLabel('left', track_name)
        plot_item.hideAxis('left')
        
        # Ensure TrackRenderingMixin is initialized
        self.TrackRenderingMixin_on_buildUI()
        
        # Add track
        self.add_track(video_datasource, name=track_name, plot_item=plot_item)
        
        return video_widget, root_graphics, plot_item, dock



if __name__ == "__main__":
    # To demo: supply a path to a valid XDF file containing EEG/LFP/continuous apparatus streams:
    # e.g. replace with your local file: demo_xdf_path = Path("/path/to/your/example.xdf")
    # Or, use main() for standard demo
    import argparse

    parser = argparse.ArgumentParser(description="Run pyPhoTimeline EEG XDF example.")
    parser.add_argument('--xdf', type=str, help='Path to XDF file to visualize EEG tracks.')
    args = parser.parse_args()

    if args.xdf is not None:
        demo_xdf_path = Path(args.xdf)

    else:
        demo_xdf_path = Path(r"E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2025-10-21T051157.400Z_eeg.xdf").resolve()
        assert demo_xdf_path.exists()


    if not demo_xdf_path.exists():
        print(f"ERROR: XDF file does not exist: {demo_xdf_path}")
        sys.exit(1)
    else:
        print(f'loading xdf file: "{demo_xdf_path.as_posix()}"')
        
    app = pg.mkQApp("pyPhoTimelineXDFExample")
    # main_all_eeg_modalities_from_xdf_file_example(demo_xdf_path)
    main_all_modalities_from_xdf_file_example(demo_xdf_path)
    sys.exit(app.exec_())
