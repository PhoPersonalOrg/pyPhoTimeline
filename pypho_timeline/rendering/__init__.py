"""Rendering package for pypho_timeline - interval/epoch rendering functionality."""

from pypho_timeline.rendering.graphics.interval_rects_item import (
    IntervalRectsItem,
    IntervalRectsItemData
)
from pypho_timeline.rendering.graphics.rectangle_helpers import (
    RectangleRenderTupleHelpers
)
from pypho_timeline.rendering.graphics.track_renderer import (
    TrackRenderer
)
from pypho_timeline.rendering.helpers.render_rectangles_helper import (
    Render2DEventRectanglesHelper
)
from pypho_timeline.rendering.mixins.epoch_rendering_mixin import (
    EpochRenderingMixin,
    RenderedEpochsItemsContainer
)
from pypho_timeline.rendering.mixins.live_window_monitoring_mixin import (
    LiveWindowEventIntervalMonitoringMixin
)
from pypho_timeline.rendering.mixins.track_rendering_mixin import (
    TrackRenderingMixin
)
from pypho_timeline.rendering.datasources.interval_datasource import (
    IntervalsDatasource
)
from pypho_timeline.rendering.datasources.track_datasource import (
    TrackDatasource,
    DetailRenderer
)
from pypho_timeline.rendering.async_detail_fetcher import (
    AsyncDetailFetcher
)
from pypho_timeline.rendering.detail_renderers import (
    VideoThumbnailDetailRenderer,
    GenericPlotDetailRenderer
)

__all__ = [
    # Graphics
    'IntervalRectsItem',
    'IntervalRectsItemData',
    'RectangleRenderTupleHelpers',
    'TrackRenderer',
    # Helpers
    'Render2DEventRectanglesHelper',
    # Mixins
    'EpochRenderingMixin',
    'RenderedEpochsItemsContainer',
    'LiveWindowEventIntervalMonitoringMixin',
    'TrackRenderingMixin',
    # Datasources
    'IntervalsDatasource',
    'TrackDatasource',
    'DetailRenderer',
    # Async fetching
    'AsyncDetailFetcher',
    # Detail renderers
    'VideoThumbnailDetailRenderer',
    'GenericPlotDetailRenderer',
]

