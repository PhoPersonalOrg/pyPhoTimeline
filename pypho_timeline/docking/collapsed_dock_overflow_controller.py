"""Footer/header chip strip mirroring pyqtgraph Dock items in collapsed state."""

from functools import partial
from typing import TYPE_CHECKING, Dict, Optional, Tuple, Callable, Any

from qtpy import QtCore, QtWidgets

if TYPE_CHECKING:
    from pypho_timeline.EXTERNAL.pyqtgraph.dockarea.Dock import Dock
    from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget


class CollapsedDockOverflowController(QtCore.QObject):
    """Shows a tool button per collapsed leaf dock; clicking expands the dock."""

    def __init__(self, contents_widget: QtWidgets.QWidget, strip_widget: Optional[QtWidgets.QWidget] = None, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent=parent)
        self._contents = contents_widget
        self._strip = strip_widget
        self._chips_layout = QtWidgets.QHBoxLayout(self._contents)
        self._chips_layout.setContentsMargins(2, 0, 2, 0)
        self._chips_layout.setSpacing(4)
        self._dock_to_button: Dict[object, QtWidgets.QToolButton] = {}
        self._dock_signal_handlers: Dict[object, Tuple[Callable[..., Any], Callable[..., Any]]] = {}
        self._nested: Optional["NestedDockAreaWidget"] = None


    def _clear_registered_docks(self) -> None:
        for dock, (on_collapse, on_close) in list(self._dock_signal_handlers.items()):
            try:
                dock.sigCollapseClicked.disconnect(on_collapse)
            except (TypeError, RuntimeError):
                pass
            try:
                dock.sigClosed.disconnect(on_close)
            except (TypeError, RuntimeError):
                pass
        self._dock_signal_handlers.clear()
        for _dock, btn in list(self._dock_to_button.items()):
            self._chips_layout.removeWidget(btn)
            btn.deleteLater()
        self._dock_to_button.clear()
        self._update_strip_visibility()


    def bind_to_nested_dock_area(self, nested: "NestedDockAreaWidget") -> None:
        if self._nested is not None:
            try:
                self._nested.sigDockAdded.disconnect(self._on_dock_added)
            except (TypeError, RuntimeError):
                pass
        self._clear_registered_docks()
        self._nested = nested
        for _name, pair in nested.get_flat_dock_item_tuple_dict().items():
            dock = pair[0]
            self._register_dock(dock)
        if hasattr(nested, "sigDockAdded"):
            nested.sigDockAdded.connect(self._on_dock_added)


    def _on_dock_added(self, _parent: object, dock: "Dock") -> None:
        self._register_dock(dock)


    def _should_skip_dock(self, dock: "Dock") -> bool:
        cfg = getattr(dock, "config", None)
        if cfg is not None:
            if getattr(cfg, "hideTitleBar", False):
                return True
            if not getattr(cfg, "showCollapseButton", True):
                return True
        meta = (getattr(cfg, "additional_metadata", None) or {}) if cfg is not None else {}
        if meta.get("type", "LEAF") != "LEAF":
            return True
        name = dock.name()
        if isinstance(name, str) and name.startswith("GROUP[") and name.endswith("]"):
            return True
        return False


    def _register_dock(self, dock: "Dock") -> None:
        if self._should_skip_dock(dock):
            return
        if dock in self._dock_to_button:
            return
        btn = QtWidgets.QToolButton(self._contents)
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        btn.setVisible(False)
        btn.clicked.connect(partial(self._on_chip_clicked, dock))

        def on_collapse_emitted(_emitted: object = None) -> None:
            self._on_collapse_toggled(dock)

        def on_close_emitted(_emitted: object = None) -> None:
            self._on_dock_closed(dock)

        dock.sigCollapseClicked.connect(on_collapse_emitted)
        dock.sigClosed.connect(on_close_emitted)
        self._dock_signal_handlers[dock] = (on_collapse_emitted, on_close_emitted)
        self._dock_to_button[dock] = btn
        self._chips_layout.addWidget(btn)
        self._sync_chip_for_dock(dock)


    def _on_collapse_toggled(self, dock: "Dock") -> None:
        self._sync_chip_for_dock(dock)


    def _sync_chip_for_dock(self, dock: "Dock") -> None:
        btn = self._dock_to_button.get(dock)
        if btn is None:
            return
        title = dock.title() or dock.name() or "?"
        btn.setText(str(title))
        btn.setToolTip("Click to expand" if getattr(dock, "contentsHidden", False) else "")
        collapsed = bool(getattr(dock, "contentsHidden", False))
        btn.setVisible(collapsed)
        self._update_strip_visibility()


    def _update_strip_visibility(self) -> None:
        visible = any(b.isVisible() for b in self._dock_to_button.values())
        if self._strip is not None:
            self._strip.setVisible(visible)


    def _on_chip_clicked(self, dock: "Dock") -> None:
        if not getattr(dock, "contentsHidden", False):
            return
        dock.toggleContentVisibility()
        if dock.label is not None:
            dock.label.updateCollapseButtonStyle(is_collapse_active=dock.contentsHidden)
        self._sync_chip_for_dock(dock)


    def _on_dock_closed(self, dock: "Dock") -> None:
        h = self._dock_signal_handlers.pop(dock, None)
        if h is not None:
            on_collapse, on_close = h
            try:
                dock.sigCollapseClicked.disconnect(on_collapse)
            except (TypeError, RuntimeError):
                pass
            try:
                dock.sigClosed.disconnect(on_close)
            except (TypeError, RuntimeError):
                pass
        btn = self._dock_to_button.pop(dock, None)
        if btn is not None:
            self._chips_layout.removeWidget(btn)
            btn.deleteLater()
        self._update_strip_visibility()

