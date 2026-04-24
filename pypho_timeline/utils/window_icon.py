"""Resolve bundled window icon paths and build QIcon for timeline windows."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

_app_default_icon_applied = False


def timeline_window_icon_path() -> Path | None:
    """Return path to bundled ``pyPhoTimeline_Icon_Screenshot.ico`` or ``.png``, or None if missing."""
    root = Path(__file__).resolve().parent.parent
    resources = root / "resources"
    ico = resources / "pyPhoTimeline_Icon_Screenshot.ico"
    if ico.is_file():
        return ico
    png = resources / "pyPhoTimeline_Icon_Screenshot.png"
    if png.is_file():
        return png
    return None



def timeline_window_icon() -> QIcon:
    """Build a :class:`QIcon` from bundled assets; returns a null icon if files are absent."""
    p = timeline_window_icon_path()
    if p is None:
        return QIcon()
    return QIcon(str(p))



def ensure_timeline_application_window_icon() -> None:
    """Set :meth:`QApplication.setWindowIcon` once so dialogs inherit the timeline icon."""
    global _app_default_icon_applied
    if _app_default_icon_applied:
        return
    app = QApplication.instance()
    icon = timeline_window_icon()
    if app is None or icon.isNull():
        return
    app.setWindowIcon(icon)
    _app_default_icon_applied = True
