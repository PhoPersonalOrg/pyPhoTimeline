"""pyPhoTimeline - A library for creating time-synchronized timeline widgets with docked tracks.

This library provides functionality for creating scrollable docked widgets (timelines) that can
display various data tracks (spikes, intervals, etc.) synchronized with a main time window.
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

__version__ = "0.1.0"

from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.core.time_synchronized_plotter_base import TimeSynchronizedPlotterBase
from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget

from pypho_timeline.docking.dock_display_configs import (
    DockDisplayColors,
    CustomDockDisplayConfig,
    CustomCyclicColorsDockDisplayConfig,
    FigureWidgetDockDisplayConfig,
    NamedColorScheme,
)
from pypho_timeline.docking.dynamic_dock_display_area import (
    DynamicDockDisplayAreaContentMixin,
    DynamicDockDisplayAreaOwningMixin,
)
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin

from pypho_timeline.widgets.custom_graphics_layout_widget import (
    CustomGraphicsLayoutWidget,
    CustomViewBox,
)

from pypho_timeline.timeline_builder import TimelineBuilder

from pypho_timeline.mixins.crosshairs_tracing_mixin import CrosshairsTracingMixin

# Rendering (interval/epoch rendering)
from pypho_timeline.rendering import (
    IntervalRectsItem,
    IntervalRectsItemData,
    RectangleRenderTupleHelpers,
    Render2DEventRectanglesHelper,
    EpochRenderingMixin,
    RenderedEpochsItemsContainer,
    LiveWindowEventIntervalMonitoringMixin,
    IntervalsDatasource,
    TrackRenderer,
    TrackRenderingMixin,
    TrackDatasource,
    DetailRenderer,
    AsyncDetailFetcher,
    VideoThumbnailDetailRenderer,
    GenericPlotDetailRenderer,
)

__all__ = [
    # Core
    'SynchronizedPlotMode',
    'TimeSynchronizedPlotterBase',
    'PyqtgraphTimeSynchronizedWidget',
    # Docking
    'DockDisplayColors',
    'CustomDockDisplayConfig',
    'CustomCyclicColorsDockDisplayConfig',
    'FigureWidgetDockDisplayConfig',
    'NamedColorScheme',
    'DynamicDockDisplayAreaContentMixin',
    'DynamicDockDisplayAreaOwningMixin',
    'NestedDockAreaWidget',
    'SpecificDockWidgetManipulatingMixin',
    # Widgets
    'CustomGraphicsLayoutWidget',
    'CustomViewBox',
    'TimelineBuilder',
    # Mixins
    'CrosshairsTracingMixin',
    # Rendering
    'IntervalRectsItem',
    'IntervalRectsItemData',
    'RectangleRenderTupleHelpers',
    'Render2DEventRectanglesHelper',
    'EpochRenderingMixin',
    'RenderedEpochsItemsContainer',
    'LiveWindowEventIntervalMonitoringMixin',
    'IntervalsDatasource',
    'TrackRenderer',
    'TrackRenderingMixin',
    'TrackDatasource',
    'DetailRenderer',
    'AsyncDetailFetcher',
    'VideoThumbnailDetailRenderer',
    'GenericPlotDetailRenderer',
]

