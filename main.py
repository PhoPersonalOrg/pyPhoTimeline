"""
Simple example demonstrating the vispy video track renderer.

This script shows how to create a timeline with video tracks using the
high-performance vispy renderer for efficient real-time rendering.
"""

from pathlib import Path
from datetime import datetime, timezone
from qtpy import QtWidgets
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.widgets import SimpleTimelineWidget
from pypho_timeline.rendering.datasources.specific import VideoTrackDatasource
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode


def main():
    """Main function demonstrating vispy video track renderer."""
    
    # Create Qt application
    app = pg.mkQApp("VispyVideoTrackExample")
    
    # Example 1: Create video track from a folder of video files
    # Replace with your actual video folder path
    video_folder_path = Path(r"M:/ScreenRecordings/EyeTrackerVR_Recordings")
    print(f"Video folder path: {video_folder_path}")


    # Specify your video folder path
    # video_folder = Path(r"E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/Videos")
    video_folder = Path(r"M:/ScreenRecordings/EyeTrackerVR_Recordings")
    assert video_folder.exists() and video_folder.is_dir()

    # Check if folder exists (for demonstration, we'll create a datasource anyway)
    if not video_folder_path.exists():
        print(f"Warning: Video folder not found: {video_folder_path}")
        print("Please update 'video_folder_path' with a valid path to your video files.")
        print("The script will still run but no videos will be displayed.\n")

        
    # Gather all video files (adjust extensions as needed)
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')
    all_videos = [p for p in video_folder.glob('*') if p.suffix.lower() in video_extensions]

    # Sort by modification time (descending), get 5 most recent
    all_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    recent_videos = all_videos[:10]
    recent_videos

    # Create the VideoTrackDatasource
    # video_ds = VideoTrackDatasource(video_paths=recent_videos)

    print(f"Recent videos: {recent_videos}")

    
    
    # Create VideoTrackDatasource with vispy renderer enabled
    print("Creating VideoTrackDatasource with vispy renderer...")
    video_datasource = VideoTrackDatasource(
        # video_folder_path=video_folder_path,
        video_paths=recent_videos,
        custom_datasource_name="Video Track (Vispy)",
        use_vispy_renderer=True,  # Enable vispy renderer
        frames_per_second=10.0,
        thumbnail_size=(128, 128)
    )
    
    # Get time range from datasource
    if not video_datasource.intervals_df.empty:
        t_start, t_end = video_datasource.total_df_start_end_times
        print(f"Video track time range: {t_start:.2f} to {t_end:.2f} seconds")
        print(f"Number of video intervals: {len(video_datasource.intervals_df)}")
    else:
        # Use default time range if no videos found
        t_start, t_end = 0.0, 100.0
        print("No video intervals found, using default time range")
    
    # Create reference datetime (for datetime axis alignment)
    reference_datetime = datetime.now(timezone.utc)
    
    # Create the timeline widget
    print("\nCreating SimpleTimelineWidget...")
    timeline = SimpleTimelineWidget(
        total_start_time=t_start,
        total_end_time=t_end,
        window_duration=min(30.0, (t_end - t_start) * 0.3),  # 30% of total range or 30s
        window_start_time=t_start,
        add_example_tracks=False,
        reference_datetime=reference_datetime
    )
    
    # Add video track with vispy renderer
    print("Adding video track with vispy renderer...")
    video_widget, root_graphics, plot_item, dock = timeline.add_video_track(
        track_name="Video Track (Vispy)",
        video_datasource=video_datasource,
        dockSize=(800, 100),
        sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA,
        use_vispy=True  # Enable vispy renderer
    )
    
    # Set window properties
    timeline.setWindowTitle("Vispy Video Track Renderer Example")
    timeline.resize(1000, 700)
    timeline.show()
    
    print("\n" + "="*60)
    print("Vispy Video Track Renderer Example")
    print("="*60)
    print("\nFeatures demonstrated:")
    print("  ✓ High-performance GPU-accelerated rendering")
    print("  ✓ Instanced rendering for efficient drawing")
    print("  ✓ Viewport culling (only visible epochs rendered)")
    print("  ✓ Real-time updates with rate limiting (~60fps)")
    print("  ✓ Datetime axis alignment")
    print("\nControls:")
    print("  - Scroll/Pan: Drag with mouse")
    print("  - Zoom: Mouse wheel")
    print("  - Hover: See video file information")
    print("\nClose the window to exit.\n")
    
    # Run the application
    sys.exit(app.exec_())


def example_with_multiple_video_tracks():
    """Example showing both vispy and pyqtgraph renderers side-by-side."""
    
    from pathlib import Path
    from datetime import datetime, timezone
    import pyphoplacecellanalysis.External.pyqtgraph as pg
    
    from pypho_timeline.widgets import SimpleTimelineWidget
    from pypho_timeline.rendering.datasources.specific import VideoTrackDatasource
    from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
    
    app = pg.mkQApp("VispyComparisonExample")
    
    video_folder_path = Path("path/to/your/video/folder")
    reference_datetime = datetime.now(timezone.utc)
    
    # Create two video datasources from the same folder
    # (In practice, you'd use different folders or filter differently)
    video_ds_vispy = VideoTrackDatasource(
        video_folder_path=video_folder_path,
        custom_datasource_name="Video Track (Vispy - GPU)",
        use_vispy_renderer=True
    )
    
    video_ds_pyqtgraph = VideoTrackDatasource(
        video_folder_path=video_folder_path,
        custom_datasource_name="Video Track (PyQtGraph)",
        use_vispy_renderer=False  # Use traditional pyqtgraph renderer
    )
    
    # Get time range
    if not video_ds_vispy.intervals_df.empty:
        t_start, t_end = video_ds_vispy.total_df_start_end_times
    else:
        t_start, t_end = 0.0, 100.0
    
    # Create timeline
    timeline = SimpleTimelineWidget(
        total_start_time=t_start,
        total_end_time=t_end,
        window_duration=min(30.0, (t_end - t_start) * 0.3),
        window_start_time=t_start,
        reference_datetime=reference_datetime
    )
    
    # Add vispy track
    timeline.add_video_track(
        track_name="Vispy Renderer",
        video_datasource=video_ds_vispy,
        dockSize=(800, 100),
        use_vispy=True
    )
    
    # Add pyqtgraph track for comparison
    timeline.add_video_track(
        track_name="PyQtGraph Renderer",
        video_datasource=video_ds_pyqtgraph,
        dockSize=(800, 100),
        use_vispy=False
    )
    
    timeline.setWindowTitle("Vispy vs PyQtGraph Comparison")
    timeline.resize(1000, 800)
    timeline.show()
    
    print("\nComparison example:")
    print("  - Top track: Vispy renderer (GPU-accelerated)")
    print("  - Bottom track: PyQtGraph renderer (CPU-based)")
    print("  - Compare performance by scrolling/zooming")
    
    sys.exit(app.exec_())


def example_with_video_paths():
    """Example using a list of specific video file paths."""
    
    from pathlib import Path
    from datetime import datetime, timezone
    import pyphoplacecellanalysis.External.pyqtgraph as pg
    
    from pypho_timeline.widgets import SimpleTimelineWidget
    from pypho_timeline.rendering.datasources.specific import VideoTrackDatasource
    from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
    
    app = pg.mkQApp("VispyVideoPathsExample")
    
    # List of specific video file paths
    video_paths = [
        Path("video1.mp4"),
        Path("video2.mp4"),
        Path("video3.mp4"),
    ]
    
    # Create datasource from specific paths
    video_datasource = VideoTrackDatasource(
        video_paths=video_paths,
        custom_datasource_name="Video Track from Paths",
        use_vispy_renderer=True,
        reference_timestamp=None  # Will use first video's start time
    )
    
    # Get time range
    if not video_datasource.intervals_df.empty:
        t_start, t_end = video_datasource.total_df_start_end_times
    else:
        t_start, t_end = 0.0, 100.0
    
    # Create timeline
    timeline = SimpleTimelineWidget(
        total_start_time=t_start,
        total_end_time=t_end,
        window_duration=min(30.0, (t_end - t_start) * 0.3),
        window_start_time=t_start
    )
    
    # Add track
    timeline.add_video_track(
        track_name="Videos from Paths",
        video_datasource=video_datasource,
        use_vispy=True
    )
    
    timeline.setWindowTitle("Vispy Video Track from File Paths")
    timeline.resize(1000, 700)
    timeline.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    import sys
    main()

