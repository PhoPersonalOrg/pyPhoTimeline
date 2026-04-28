import importlib
from typing import Any, List

_LAZY_EXPORT_MODULES = {
    'MotionTrackDatasource': 'pypho_timeline.rendering.datasources.specific.motion',
    'MotionPlotDetailRenderer': 'pypho_timeline.rendering.datasources.specific.motion',
    'VideoTrackDatasource': 'pypho_timeline.rendering.datasources.specific.video',
    'VideoThumbnailDetailRenderer': 'pypho_timeline.rendering.datasources.specific.video',
    'video_metadata_to_intervals_df': 'pypho_timeline.rendering.datasources.specific.video',
    'VideoMetadataParser': 'phopylslhelper.file_metadata_caching.video_metadata',
    'EEGTrackDatasource': 'pypho_timeline.rendering.datasources.specific.eeg',
    'EEGFPTrackDatasource': 'pypho_timeline.rendering.datasources.specific.eeg',
    'EEGPlotDetailRenderer': 'pypho_timeline.rendering.datasources.specific.eeg',
    'LSLStreamReceiver': 'pypho_timeline.rendering.datasources.specific.lsl',
    'LiveEEGTrackDatasource': 'pypho_timeline.rendering.datasources.specific.lsl',
}

__all__ = [
    'MotionTrackDatasource',
    'MotionPlotDetailRenderer',
    'VideoTrackDatasource',
    'VideoThumbnailDetailRenderer',
    'video_metadata_to_intervals_df',
    'VideoMetadataParser',
    'EEGTrackDatasource',
    'EEGFPTrackDatasource',
    'EEGPlotDetailRenderer',
    'LSLStreamReceiver',
    'LiveEEGTrackDatasource',
]


def __getattr__(name: str) -> Any:
    modname = _LAZY_EXPORT_MODULES.get(name)
    if modname is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = importlib.import_module(modname)
    return getattr(mod, name)


def __dir__() -> List[str]:
    return sorted(__all__)