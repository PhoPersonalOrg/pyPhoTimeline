"""Detail renderers for timeline track detailed views."""

import importlib
from typing import Any, List

from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer, IntervalPlotDetailRenderer, DataframePlotDetailRenderer
from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer

# Lazily resolve modality-specific renderers to avoid circular imports with datasources.specific
# (e.g. motion.py imports generic_plot_renderer while this package is initializing).
_LAZY_DETAIL_RENDERER_MODULES = {
    'MotionPlotDetailRenderer': 'pypho_timeline.rendering.datasources.specific.motion',
    'VideoThumbnailDetailRenderer': 'pypho_timeline.rendering.datasources.specific.video',
    'EEGPlotDetailRenderer': 'pypho_timeline.rendering.datasources.specific.eeg',
}

__all__ = [
    'MotionPlotDetailRenderer',
    'VideoThumbnailDetailRenderer',
    'EEGPlotDetailRenderer',
    'GenericPlotDetailRenderer', 'IntervalPlotDetailRenderer', 'DataframePlotDetailRenderer', 'LogTextDataFramePlotDetailRenderer',
]


def __getattr__(name: str) -> Any:
    modname = _LAZY_DETAIL_RENDERER_MODULES.get(name)
    if modname is not None:
        mod = importlib.import_module(modname)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    return sorted(__all__)
