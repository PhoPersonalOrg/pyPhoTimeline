# MainTimelineWindow.py
# Generated from c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.ui automatically by PhoPyQtClassGenerator VSCode Extension
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Union, Any, TYPE_CHECKING
from qtpy import QtWidgets, QtCore

## required stream_viewer implementations
from stream_viewer.data import LSLDataSource
from stream_viewer.data import LSLStreamInfoTableModel
from stream_viewer.widgets import StreamStatusQMLWidget

if TYPE_CHECKING:
    from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget

## IMPORTS:
from pypho_timeline.utils.logging_util import get_rendering_logger


_logger = get_rendering_logger(__name__)


class LSLConnectedViewerMixin:
    """ Description of what this mixin does

    Factored out from `LSLViewer` which originally implemented it all on its own
    
    Requires at minimum:
        List of required attributes/methods
    
    Creates:
        List of attributes/methods this mixin creates
        
        
    Known Usages:
        List of classes that use this mixin
    
    """
    def LSLConnectedViewerMixin_on_init(self, settings_path: Optional[Path]=None, **kwargs):
        """ perform any parameters setting/checking during init """
        self._open_renderers = []  # List of renderer keys (rend_cls :: strm_name :: int)
        self._plugin_dirs = {'renderers': [], 'widgets': []}  # Dict of lists of directories to search for plugins
                                                              #  in addition to default search dir of
                                                              #  ~/.stream_viewer/plugins/{renderers|widgets}
        self._monitor_sources = {}

        home_dir = Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.HomeLocation))
        self._settings_path = home_dir / '.stream_viewer' / 'lsl_viewer.ini'
        if settings_path is not None:
            settings_path = Path(settings_path)
            if not settings_path.exists():
                # Try only the filename in the default folder.
                settings_path = home_dir / '.stream_viewer' / settings_path.name
            if settings_path.exists():
                self._settings_path = settings_path

        # Set the data model for the stream status view. This handles its own list of streams.
        self.stream_status_model = LSLStreamInfoTableModel(refresh_interval=5.0)
        # Create the stream status panel.
        self.stream_status_widget = None



    def LSLConnectedViewerMixin_on_setup(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        pass


    def setup_status_panel(self):
        dock = QtWidgets.QDockWidget()
        dock.setObjectName("StatusPanel")
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea)
        dock.setMinimumWidth(300)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetClosable)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.setWidget(self.stream_status_widget)
        dock.setFloating(False)
        # Prevent the dock from floating by monitoring topLevelChanged signal
        dock.topLevelChanged.connect(lambda floating: dock.setFloating(False) if floating else None)


    def LSLConnectedViewerMixin_on_buildUI(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        # Create the stream status panel.
        self.stream_status_widget = StreamStatusQMLWidget(self.stream_status_model)
        # self.stream_status_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
        #                                         QtWidgets.QSizePolicy.MinimumExpanding)
        self.stream_status_widget.stream_activated.connect(self.on_stream_activated)
        self.stream_status_widget.stream_added.connect(self.on_stream_added)
        self.setup_status_panel()

    

    def LSLConnectedViewerMixin_on_destroy(self):
        """ perform teardown/destruction of anything that needs to be manually removed or released """
        pass


    @QtCore.Slot(dict)
    def on_stream_added(self, strm):
        self._monitor_sources[strm['uid']] = LSLDataSource(strm, auto_start=True, timer_interval=1000, monitor_only=True)
        self._monitor_sources[strm['uid']].rate_updated.connect(
            functools.partial(self.stream_status_widget.model.handleRateUpdated, stream_data=strm)
        )

    @QtCore.Slot(dict)
    def on_stream_activated(self, sources, renderer_name=None, renderer_kwargs={}):
        return self.on_stream_activated(sources, renderer_name=renderer_name, renderer_kwargs=renderer_kwargs, forced_rend_key=None)


    def on_stream_activated(self, sources, renderer_name=None, renderer_kwargs={}, forced_rend_key=None):
        # Normalize renderer_name: if not provided then use a popup combo box.
        raise NotImplementedError(f'Implementor must override!')
