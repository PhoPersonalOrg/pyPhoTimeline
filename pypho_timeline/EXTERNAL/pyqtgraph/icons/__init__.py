import os.path as op
import warnings

from ..Qt import QtGui, QtWidgets

__all__ = ['getGraphIcon', 'getGraphPixmap']

_ICON_REGISTRY = {}


class GraphIcon:
    """An icon place holder for lazy loading of QIcons

    The icon must reside in the icons folder and the path refers to the full
    name including suffix of the icon file, e.g.:

        tiny = GraphIcon("tiny.png")

    Icons can be later retrieved via the function `getGraphIcon` and providing
    the name:

        tiny = getGraphIcon("tiny")
    """

    def __init__(self, path):
        self._path = path
        name = path.split('.')[0]
        _ICON_REGISTRY[name] = self
        self._icon = None

    def _build_qicon(self):
        icon = QtGui.QIcon(op.join(op.dirname(__file__), self._path))
        name = self._path.split('.')[0]
        _ICON_REGISTRY[name] = icon
        self._icon = icon

    @property
    def qicon(self):
        if self._icon is None:
            self._build_qicon()

        return self._icon


def getGraphIcon(name):
    """Return a `PyQtGraph` icon from the registry by `name`"""
    icon = _ICON_REGISTRY[name]
    if isinstance(icon, GraphIcon):
        icon = icon.qicon
        _ICON_REGISTRY[name] = icon

    return icon


def getGraphPixmap(name, size=(20, 20)):
    """Return a `QPixmap` from the registry by `name`"""
    icon = getGraphIcon(name)

    return icon.pixmap(*size)


def getPixmap(name, size=(20, 20)):
    """Historic `getPixmap` function

    (eg. getPixmap('auto') loads pyqtgraph/icons/auto.png)
    """
    warnings.warn(
        "'getPixmap' is deprecated and will be removed soon, "
        "please use `getGraphPixmap` in the future",
        DeprecationWarning, stacklevel=2)
    return getGraphPixmap(name, size=size)


# Note: List all graph icons here (sorted by filename; icons.png renamed to icons-raster.png so icons.svg can use key "icons").
applicationDockTab = GraphIcon("application-dock-tab.png")
applicationRename = GraphIcon("application-rename.png")
applicationTileHorizontal = GraphIcon("application-tile-horizontal.png")
applicationWave = GraphIcon("application-wave.png")
auto = GraphIcon("auto.png")
categoryGroup = GraphIcon("category-group.png")
commentts = GraphIcon("commentts.png")
ctrl = GraphIcon("ctrl.png")
default = GraphIcon("default.png")
filmTimeline = GraphIcon("film-timeline.png")
film = GraphIcon("film.png")
films = GraphIcon("films.png")
form = GraphIcon("form.png")
globeGreen = GraphIcon("globe-green.png")
iconsRaster = GraphIcon("icons-raster.png")
icons = GraphIcon("icons.svg")
invisibleEye = GraphIcon("invisibleEye.svg")
lock = GraphIcon("lock.png")
log_scroll = GraphIcon("log_scroll.png")
settings_gear = GraphIcon("settings_gear.png")
settings_wrench = GraphIcon("settings_wrench.png")
settings = GraphIcon("settings.png")
stickyNotesStack = GraphIcon("sticky-notes-stack.png")
tableHeatmap = GraphIcon("table-heatmap.png")
table = GraphIcon("table.png")
tablesStacks = GraphIcon("tables-stacks.png")
uiToolbar = GraphIcon("ui-toolbar.png")
