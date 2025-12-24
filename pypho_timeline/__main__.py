"""
Example usage of pyPhoTimeline library.

This demonstrates how to create a timeline with docked tracks that can display
time-synchronized data.
"""

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
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource
from pypho_timeline.rendering.detail_renderers import PositionPlotDetailRenderer, VideoThumbnailDetailRenderer
from pypho_timeline.rendering.mixins.track_rendering_mixin import TrackRenderingMixin
from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots


class PositionTrackDatasource(BaseTrackDatasource):
    """Example TrackDatasource for position data.
    
    Inherits from BaseTrackDatasource and implements all required methods for
    displaying position data with async detail loading.
    """
    
    def __init__(self, position_df: pd.DataFrame, intervals_df: pd.DataFrame):
        """Initialize with position data and intervals.
        
        Args:
            position_df: DataFrame with columns ['t', 'x', 'y'] (or ['t', 'x'] for 1D)
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
        """
        super().__init__()
        self.position_df = position_df
        self.intervals_df = intervals_df.copy()
        self.custom_datasource_name = "PositionTrack"
        
        # Add visualization columns to intervals
        self.intervals_df['series_vertical_offset'] = 0.0
        self.intervals_df['series_height'] = 1.0
        
        # Create pens and brushes
        color = pg.mkColor('blue')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.intervals_df['pen'] = [pen] * len(self.intervals_df)
        self.intervals_df['brush'] = [brush] * len(self.intervals_df)
    
    @property
    def df(self) -> pd.DataFrame:
        return self.intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> tuple:
        if len(self.intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self.intervals_df['t_start'].min()
        t_end = (self.intervals_df['t_start'] + self.intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self.intervals_df['t_start'] + self.intervals_df['t_duration'] >= new_start) & \
               (self.intervals_df['t_start'] <= new_end)
        return self.intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self.intervals_df = dataframe_vis_columns_function(self.intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self.intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Fetch position data for an interval."""
        t_start = interval['t_start']
        t_end = t_start + interval['t_duration']
        mask = (self.position_df['t'] >= t_start) & (self.position_df['t'] < t_end)
        return self.position_df[mask].copy()
    
    def get_detail_renderer(self):
        """Get detail renderer for position data."""
        return PositionPlotDetailRenderer(pen_color='cyan', pen_width=2, y_column='y' if 'y' in self.position_df.columns else None)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"position_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


class VideoTrackDatasource(BaseTrackDatasource):
    """Example TrackDatasource for video data.
    
    Inherits from BaseTrackDatasource and implements all required methods for
    displaying video intervals with async detail loading.
    """
    
    def __init__(self, video_intervals_df: pd.DataFrame):
        """Initialize with video intervals.
        
        Args:
            video_intervals_df: DataFrame with columns ['t_start', 't_duration', 'video_path']
        """
        super().__init__()
        self.video_intervals_df = video_intervals_df.copy()
        self.custom_datasource_name = "VideoTrack"
        
        # Add visualization columns
        self.video_intervals_df['series_vertical_offset'] = 0.0
        self.video_intervals_df['series_height'] = 50.0
        
        # Create pens and brushes
        color = pg.mkColor('green')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.video_intervals_df['pen'] = [pen] * len(self.video_intervals_df)
        self.video_intervals_df['brush'] = [brush] * len(self.video_intervals_df)
    
    @property
    def df(self) -> pd.DataFrame:
        return self.video_intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> tuple:
        if len(self.video_intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self.video_intervals_df['t_start'].min()
        t_end = (self.video_intervals_df['t_start'] + self.video_intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self.video_intervals_df['t_start'] + self.video_intervals_df['t_duration'] >= new_start) & \
               (self.video_intervals_df['t_start'] <= new_end)
        return self.video_intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self.video_intervals_df = dataframe_vis_columns_function(self.video_intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self.video_intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> dict:
        """Fetch video frames for an interval (simulated with random images)."""
        # In a real implementation, this would load video frames
        # For demo, generate synthetic frame data
        n_frames = max(1, int(interval['t_duration'] * 10))  # 10 fps
        frames = []
        for i in range(n_frames):
            # Generate a simple colored frame
            frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            frames.append(frame)
        return {'frames': frames, 'timestamps': np.linspace(interval['t_start'], interval['t_start'] + interval['t_duration'], n_frames)}
    
    def get_detail_renderer(self):
        """Get detail renderer for video."""
        return VideoThumbnailDetailRenderer(thumbnail_height=50.0, spacing=0.1)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"video_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


class SimpleTimelineWidget(TrackRenderingMixin, SpecificDockWidgetManipulatingMixin, QtWidgets.QWidget):
    """A simple example timeline widget that demonstrates pyPhoTimeline usage."""
    
    # Signal emitted when the time window changes
    window_scrolled = QtCore.Signal(float, float)
    
    @property
    def interval_rendering_plots(self):
        """Return list of plots for interval rendering."""
        # Return all plot items from matplotlib_view_widgets
        plots = []
        for widget in self.ui.matplotlib_view_widgets.values():
            plots.append(widget.getRootPlotItem())
        return plots
    
    def __init__(self, total_start_time=0.0, total_end_time=100.0, window_duration=10.0, window_start_time=30.0, parent=None):
        super().__init__(parent)
        
        # Initialize UI container
        self.ui = PhoUIContainer()
        self.ui.matplotlib_view_widgets = {}
        self.ui.connections = {}
        
        # Initialize plots_data and plots for mixins
        self.plots_data = RenderPlotsData(name='SimpleTimelineWidget')
        self.plots = PyqtgraphRenderPlots(name='SimpleTimelineWidget')
        
        # Time window properties
        self.total_data_start_time = total_start_time
        self.total_data_end_time = total_end_time
        self.active_window_start_time = window_start_time
        self.active_window_end_time = window_start_time + window_duration
        
        # Create a simple time window object (mimicking spikes_window)
        class SimpleTimeWindow:
            def __init__(self, start, end, window_dur, window_start):
                self.total_df_start_end_times = (start, end)
                self.active_window_start_time = window_start
                self.active_window_end_time = window_start + window_dur
                self.active_time_window = (window_start, window_start + window_dur)
                self.window_duration = window_dur
                
            def update_window_start_end(self, start_t, end_t):
                self.active_window_start_time = start_t
                self.active_window_end_time = end_t
                self.active_time_window = (start_t, end_t)
        
        self.spikes_window = SimpleTimeWindow(
            total_start_time, total_end_time, window_duration, window_start_time
        )
        
        # Initialize plots_data and plots BEFORE setupUI (needed by mixins)
        # Initialize track rendering mixin
        self.TrackRenderingMixin_on_init()
        self.TrackRenderingMixin_on_setup()
        
        # Setup UI (this will call add_example_tracks which uses the mixins)
        self.setupUI()
        
    def setupUI(self):
        """Setup the user interface."""
        # Create main layout
        self.ui.layout = QtWidgets.QVBoxLayout(self)
        self.ui.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the dock area container
        self.ui.dynamic_docked_widget_container = NestedDockAreaWidget()
        self.ui.dynamic_docked_widget_container.setObjectName("dynamic_docked_widget_container")
        
        # Add to layout
        self.ui.layout.addWidget(self.ui.dynamic_docked_widget_container)
        
        # Add some example tracks
        self.add_example_tracks()
        
    def add_example_tracks(self):
        """Add example timeline tracks to demonstrate functionality."""
        
        # Track 1: Overview track (shows all data, no sync)
        print("Adding overview track...")
        overview_widget, root_graphics, plot_item, dock = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='overview',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.NO_SYNC
        )
        
        # Set the overview to show the full time range
        plot_item.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item.setYRange(0, 10, padding=0)
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setLabel('left', 'Overview')
        
        # Add some sample data to the overview
        x_data = np.linspace(self.total_data_start_time, self.total_data_end_time, 100)
        y_data = 5 + 3 * np.sin(2 * np.pi * x_data / 20)
        plot_item.plot(x_data, y_data, pen='y', name='overview_data')
        
        # Track 2: Window-synchronized track (syncs with active window)
        print("Adding window-synchronized track...")
        window_widget, root_graphics2, plot_item2, dock2 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='window_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_WINDOW
        )
        
        # Set initial range to match the active window
        plot_item2.setXRange(self.active_window_start_time, self.active_window_end_time, padding=0)
        plot_item2.setYRange(0, 10, padding=0)
        plot_item2.setLabel('bottom', 'Time', units='s')
        plot_item2.setLabel('left', 'Window Track')
        
        # Add sample data
        x_data2 = np.linspace(self.total_data_start_time, self.total_data_end_time, 200)
        y_data2 = 5 + 2 * np.cos(2 * np.pi * x_data2 / 15)
        plot_item2.plot(x_data2, y_data2, pen='c', name='window_data')
        
        # Track 3: Global data track (one-time sync to global range)
        print("Adding global data track...")
        global_widget, root_graphics3, plot_item3, dock3 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='global_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        # This will be set automatically by the sync, but we can set it manually too
        plot_item3.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item3.setYRange(0, 10, padding=0)
        plot_item3.setLabel('bottom', 'Time', units='s')
        plot_item3.setLabel('left', 'Global Track')
        
        # Add sample data
        x_data3 = np.linspace(self.total_data_start_time, self.total_data_end_time, 150)
        y_data3 = 5 + 4 * np.sin(2 * np.pi * x_data3 / 25)
        plot_item3.plot(x_data3, y_data3, pen='m', name='global_data')
        
        # Track 4: Interval rectangles track (shows time intervals as rectangles)
        print("Adding interval rectangles track...")
        intervals_widget, root_graphics4, plot_item4, dock4 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='intervals_track',
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        # Set range to show full time range
        plot_item4.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item4.setYRange(0, 5, padding=0)
        plot_item4.setLabel('bottom', 'Time', units='s')
        plot_item4.setLabel('left', 'Intervals')
        plot_item4.hideAxis('left')  # Hide Y-axis for cleaner look
        
        # Create sample interval data
        # Intervals at different vertical positions with different colors
        interval_data = []
        
        # Series 1: Red intervals at y=1
        intervals_1 = [
            (10.0, 1.0, 0.5, 5.0, 0.8),  # (start, y_offset, duration, height, alpha)
            (15.0, 1.0, 0.5, 5.0, 0.8),
            (20.0, 1.0, 0.5, 5.0, 0.8),
            (35.0, 1.0, 0.5, 5.0, 0.8),
            (50.0, 1.0, 0.5, 5.0, 0.8),
            (65.0, 1.0, 0.5, 5.0, 0.8),
            (80.0, 1.0, 0.5, 5.0, 0.8),
        ]
        
        # Series 2: Green intervals at y=2
        intervals_2 = [
            (12.0, 2.0, 1.0, 4.0, 0.7),
            (25.0, 2.0, 1.0, 4.0, 0.7),
            (40.0, 2.0, 1.0, 4.0, 0.7),
            (55.0, 2.0, 1.0, 4.0, 0.7),
            (70.0, 2.0, 1.0, 4.0, 0.7),
        ]
        
        # Series 3: Blue intervals at y=3
        intervals_3 = [
            (5.0, 3.0, 2.0, 3.0, 0.6),
            (30.0, 3.0, 2.0, 3.0, 0.6),
            (60.0, 3.0, 2.0, 3.0, 0.6),
            (85.0, 3.0, 2.0, 3.0, 0.6),
        ]
        
        # Create pens and brushes for each series
        red_color = pg.mkColor('r')
        red_color.setAlphaF(0.8)
        red_pen = pg.mkPen(red_color, width=2)
        red_brush = pg.mkBrush(red_color)
        
        green_color = pg.mkColor('g')
        green_color.setAlphaF(0.7)
        green_pen = pg.mkPen(green_color, width=2)
        green_brush = pg.mkBrush(green_color)
        
        blue_color = pg.mkColor('b')
        blue_color.setAlphaF(0.6)
        blue_pen = pg.mkPen(blue_color, width=2)
        blue_brush = pg.mkBrush(blue_color)
        
        # Add intervals from series 1 (red)
        for start, y_offset, duration, height, alpha in intervals_1:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=red_pen,
                brush=red_brush,
                label=f"Event at {start:.1f}s"
            ))
        
        # Add intervals from series 2 (green)
        for start, y_offset, duration, height, alpha in intervals_2:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=green_pen,
                brush=green_brush,
                label=f"Interval at {start:.1f}s"
            ))
        
        # Add intervals from series 3 (blue)
        for start, y_offset, duration, height, alpha in intervals_3:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=blue_pen,
                brush=blue_brush,
                label=f"Long interval at {start:.1f}s"
            ))
        
        # Create the IntervalRectsItem and add it to the plot
        interval_rects_item = IntervalRectsItem(interval_data)
        plot_item4.addItem(interval_rects_item)
        
        # Store reference for potential updates
        self.ui.intervals_item = interval_rects_item
        
        # Track 5: Position track with async detail loading
        print("Adding position track with async detail loading...")
        position_widget, root_graphics5, plot_item5, dock5 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='position_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        plot_item5.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item5.setYRange(-5, 5, padding=0)
        plot_item5.setLabel('bottom', 'Time', units='s')
        plot_item5.setLabel('left', 'Position Track')
        
        # Create sample position data
        position_times = np.linspace(self.total_data_start_time, self.total_data_end_time, 1000)
        position_x = 2 * np.sin(2 * np.pi * position_times / 20)
        position_y = 2 * np.cos(2 * np.pi * position_times / 20)
        position_df = pd.DataFrame({'t': position_times, 'x': position_x, 'y': position_y})
        
        # Create intervals (every 10 seconds)
        interval_starts = np.arange(self.total_data_start_time, self.total_data_end_time, 10.0)
        intervals_df = pd.DataFrame({
            't_start': interval_starts,
            't_duration': [10.0] * len(interval_starts)
        })
        
        # Create position track datasource
        position_datasource = PositionTrackDatasource(position_df, intervals_df)
        
        # Add track (this will initialize track rendering)
        self.TrackRenderingMixin_on_buildUI()
        self.add_track(position_datasource, name='position_track', plot_item=plot_item5)
        
        # Track 6: Video track with async detail loading
        print("Adding video track with async detail loading...")
        video_widget, root_graphics6, plot_item6, dock6 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='video_track',
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        plot_item6.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item6.setYRange(0, 60, padding=0)
        plot_item6.setLabel('bottom', 'Time', units='s')
        plot_item6.setLabel('left', 'Video Track')
        plot_item6.hideAxis('left')
        
        # Create video intervals
        video_intervals_df = pd.DataFrame({
            't_start': [15.0, 35.0, 55.0, 75.0],
            't_duration': [5.0, 5.0, 5.0, 5.0],
            'video_path': ['video1.mp4', 'video2.mp4', 'video3.mp4', 'video4.mp4']
        })
        
        # Create video track datasource
        video_datasource = VideoTrackDatasource(video_intervals_df)
        
        # Add track
        self.add_track(video_datasource, name='video_track', plot_item=plot_item6)
        
    def simulate_window_scroll(self, new_start_time):
        """Simulate scrolling the time window (for demonstration)."""
        new_end_time = new_start_time + (self.active_window_end_time - self.active_window_start_time)
        self.active_window_start_time = new_start_time
        self.active_window_end_time = new_end_time
        self.spikes_window.update_window_start_end(new_start_time, new_end_time)
        
        # Emit the signal to update synchronized tracks
        self.window_scrolled.emit(new_start_time, new_end_time)
        print(f"Window scrolled to: {new_start_time:.2f} - {new_end_time:.2f}")


def main():
    """Main function demonstrating pyPhoTimeline usage."""
    print("=" * 60)
    print("pyPhoTimeline Example")
    print("=" * 60)
    
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


if __name__ == "__main__":
    main()

