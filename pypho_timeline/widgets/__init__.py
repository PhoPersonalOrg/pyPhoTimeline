"""Custom widgets for timeline rendering."""

from pypho_timeline.widgets.custom_graphics_layout_widget import (
    CustomGraphicsLayoutWidget,
    CustomViewBox,
)

# Lazy import to avoid circular dependency
# simple_timeline_widget imports from docking modules which import from core modules
# that import from widgets.custom_graphics_layout_widget, creating a circular dependency
# when widgets.__init__.py tries to import simple_timeline_widget during module initialization
def _lazy_import_simple_timeline():
    """Lazy import of simple_timeline_widget to avoid circular dependencies."""
    from pypho_timeline.widgets.simple_timeline_widget import (
        SimpleTimelineWidget,
        modality_channels_dict,
        modality_sfreq_dict,
        perform_process_all_streams,
    )
    return SimpleTimelineWidget, modality_channels_dict, modality_sfreq_dict, perform_process_all_streams

# Import lazily on first access
_SimpleTimelineWidget = None
_modality_channels_dict = None
_modality_sfreq_dict = None
_perform_process_all_streams = None

def __getattr__(name):
    """Lazy loading of simple_timeline_widget exports."""
    global _SimpleTimelineWidget, _modality_channels_dict, _modality_sfreq_dict, _perform_process_all_streams
    
    if name in ('SimpleTimelineWidget', 'modality_channels_dict', 'modality_sfreq_dict', 'perform_process_all_streams'):
        if _SimpleTimelineWidget is None:
            _SimpleTimelineWidget, _modality_channels_dict, _modality_sfreq_dict, _perform_process_all_streams = _lazy_import_simple_timeline()
        
        if name == 'SimpleTimelineWidget':
            return _SimpleTimelineWidget
        elif name == 'modality_channels_dict':
            return _modality_channels_dict
        elif name == 'modality_sfreq_dict':
            return _modality_sfreq_dict
        elif name == 'perform_process_all_streams':
            return _perform_process_all_streams
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'CustomGraphicsLayoutWidget',
    'CustomViewBox',
    'SimpleTimelineWidget',
    'modality_channels_dict',
    'modality_sfreq_dict',
    'perform_process_all_streams',
]

