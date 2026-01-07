"""
Example usage of pyPhoTimeline library.

This demonstrates how to create a timeline with docked tracks that can display
time-synchronized data.
"""

# Compatibility shim for scipy.integrate.simps -> simpson
# simps was deprecated and removed in SciPy 1.12+, replaced with simpson
# This must be imported before any other modules that might use simps
try:
    from scipy.integrate import simps
except ImportError:
    # simps doesn't exist, provide it as an alias to simpson
    try:
        from scipy.integrate import simpson
        import scipy.integrate
        scipy.integrate.simps = simpson
    except ImportError:
        # If simpson also doesn't exist, we can't fix it
        pass

from pathlib import Path
from re import S
import sys
import numpy as np
import pandas as pd
from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource, PositionTrackDatasource, VideoTrackDatasource
from pypho_timeline.rendering.detail_renderers import MotionPlotDetailRenderer, PositionPlotDetailRenderer, VideoThumbnailDetailRenderer, GenericPlotDetailRenderer
from pypho_timeline.rendering.mixins.track_rendering_mixin import TrackRenderingMixin
from pypho_timeline.utils.logging_util import configure_logging

from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots

from pypho_timeline.widgets import SimpleTimelineWidget, perform_process_all_streams, modality_channels_dict, modality_sfreq_dict


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
    print("=" * 60)
    print(f"pyPhoTimeline - Load all modalities from XDF: {xdf_file_path}")
    print("=" * 60)

    # Configure logging for all pypho_timeline components (outputs to both stdout and file)
    import logging
    log_file = Path("timeline_rendering.log")
    configure_logging(
        log_level=logging.DEBUG,
        log_file=log_file,
        log_to_console=True,
        log_to_file=True
    )
    print(f"Logging configured for all pypho_timeline modules - output to console and {log_file}")

    # --- 1. Load the XDF file (using pyxdf) ---
    import pyxdf

    print(f"Loading XDF file: {xdf_file_path} ...")
    streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
    print(f"Streams loaded: {[s['info']['name'][0] for s in streams]}")
    print(f"File Header: {file_header}")

    # --- 2. Inspect and extract EEG/continuous data streams ---
    all_streams, all_streams_datasources = perform_process_all_streams(streams=streams)

    if not all_streams:
        print("No streams found in XDF file.")
        return

    print(f"Found {len(all_streams)} streams: {[a_name for a_name in list(all_streams_datasources.keys())]}")

    
    active_datasources_dict = {k:v for k, v in all_streams_datasources.items() if v is not None}
    active_datasource_list = list(active_datasources_dict.values())
    print(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")

    total_start_time: float = np.nanmin([ds.total_df_start_end_times[0] for ds in active_datasource_list])
    total_end_time: float = np.nanmax([ds.total_df_start_end_times[1] for ds in active_datasource_list])
    # window_duration: float = 10.0
    window_duration: float = total_end_time - total_start_time
    window_duration = max(window_duration, 10.0)

    # --- 4. Create the timeline widget and add EEG tracks ---
    timeline = SimpleTimelineWidget(
        total_start_time=total_start_time,
        total_end_time=total_end_time,
        window_duration=window_duration,
        window_start_time=total_start_time,
        add_example_tracks=False  # Don't add example tracks for XDF data
    )

    # Create plot widgets for each EEG stream and add tracks
    for datasource in active_datasource_list:
        # Create a plot widget for this track
        a_detail_renderer = datasource.get_detail_renderer()

        # The getOptionsPanel() method will be called by the dock when needed
        # No need to set optionsPanel attribute if getOptionsPanel() is implemented

        ## if we provide a valid `optionsPanel: Optional[QWidget]` here on the widget the button will automatically show up on the dock
        track_widget, a_root_graphics, a_plot_item, a_dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(
            name=datasource.custom_datasource_name,
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        assert a_detail_renderer is not None
        track_widget.set_track_renderer(a_detail_renderer)
        # Explicitly set the attribute (not just rely on getOptionsPanel())
        track_widget.optionsPanel = track_widget.getOptionsPanel()

        # Try to force dock to update button visibility
        a_dock.updateWidgetsHaveOptionsPanel()

        a_dock.update()  # May refresh the title bar
        # Or if available:
        if hasattr(a_dock, 'updateTitleBar') or hasattr(a_dock, 'refresh'):
            a_dock.updateTitleBar()  # or refresh()

        

        # Set the plot to show the full time range
        a_plot_item.setXRange(
            timeline.total_data_start_time, 
            timeline.total_data_end_time, 
            padding=0
        )
        a_plot_item.setYRange(0, 1, padding=0)
        a_plot_item.setLabel('bottom', 'Time', units='s')
        a_plot_item.setLabel('left', datasource.custom_datasource_name)
        a_plot_item.hideAxis('left')  # Hide Y-axis for cleaner look
        
        # Add the track to the plot
        a_track_name: str = datasource.custom_datasource_name
        timeline.add_track(
            datasource,
            name=a_track_name,
            plot_item=a_plot_item
        )

        # ## after adding the track, try to add/render the detailed data if possible (currently hardcoded). 
        # try:
        #     a_renderer = timeline.track_renderers[a_track_name]
        #     a_detail_renderer = a_renderer.detail_renderer # MotionPlotDetailRenderer 
        #     a_ds = timeline.track_datasources[a_track_name]
        #     # interval = a_ds.intervals_df
        #     interval = a_ds.get_overview_intervals()

        #     extant_graphics_objects = timeline.plots.render_detail_graphics_objects.get(a_track_name, [])
        #     if extant_graphics_objects:
        #         ## remove existing
        #         a_detail_renderer.clear_detail(plot_item=a_plot_item, graphics_objects=extant_graphics_objects)


        #     graphics_objects = a_detail_renderer.render_detail(plot_item=a_plot_item, interval=interval, detail_data=a_ds.detailed_df) # List[PlotDataItem]
        #     timeline.plots.render_detail_graphics_objects[a_track_name] = graphics_objects

        # except (ValueError, AttributeError, KeyError, IndexError) as e:
        #     print(f'\tERROR for a_track_name: "{a_track_name}" while trying to add `a_detail_renderer.render_detail(...) {e}')
        

    ## END for datasource in active_datasource_list...

    timeline.setWindowTitle(f"pyPhoTimeline - ALL Modalities from XDF: {xdf_file_path.name}")
    timeline.resize(1000, 800)
    timeline.show()

    print("\nTimeline widget created with tracks from XDF:")
    for ds in active_datasource_list:
        print(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")

    print("\nScroll on the timeline to see loaded EEG intervals for each stream.")
    print("Close the window to exit.\n")
    return timeline

    




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
