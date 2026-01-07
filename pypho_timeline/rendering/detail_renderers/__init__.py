"""Detail renderers for timeline track detailed views."""

# Import modality-specific renderers from datasources.specific (consolidated pattern)
from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer
from pypho_timeline.rendering.datasources.specific.position import PositionPlotDetailRenderer
from pypho_timeline.rendering.datasources.specific.video import VideoThumbnailDetailRenderer
from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer
# Generic renderers remain in detail_renderers/ (shared utilities)
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer, IntervalPlotDetailRenderer, DataframePlotDetailRenderer
from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer

__all__ = [
    'MotionPlotDetailRenderer',
    'PositionPlotDetailRenderer',
    'VideoThumbnailDetailRenderer',
    'EEGPlotDetailRenderer',
    'GenericPlotDetailRenderer', 'IntervalPlotDetailRenderer', 'DataframePlotDetailRenderer', 'LogTextDataFramePlotDetailRenderer',
]

