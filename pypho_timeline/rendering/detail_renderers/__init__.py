"""Detail renderers for timeline track detailed views."""

from pypho_timeline.rendering.detail_renderers.motion_plot_renderer import MotionPlotDetailRenderer
from pypho_timeline.rendering.detail_renderers.position_plot_renderer import PositionPlotDetailRenderer
from pypho_timeline.rendering.detail_renderers.video_thumbnail_renderer import VideoThumbnailDetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

__all__ = [
    'MotionPlotDetailRenderer',
    'PositionPlotDetailRenderer',
    'VideoThumbnailDetailRenderer',
    'GenericPlotDetailRenderer',
]

