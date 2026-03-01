"""Minimal DockDisplayConfig for dock title bar styling (no pyphoplacecellanalysis dependency)."""
from typing import Callable, Dict, Optional
from attrs import define, field, Factory


@define(slots=False)
class DockDisplayConfig(object):
    """Holds the display and configuration options for a Dock, such as how to format its title bar (color and font), whether it's closable, etc."""
    showCloseButton: bool = field(default=True)
    showCollapseButton: bool = field(default=True)
    showGroupButton: bool = field(default=False)
    showOrientationButton: bool = field(default=False)
    showTimelineSyncModeButton: bool = field(default=True)
    showOptionsButton: bool = field(default=False)
    hideTitleBar: bool = field(default=False)
    fontSize: str = field(default='10px')
    corner_radius: str = field(default='2px')
    custom_get_stylesheet_fn: Callable = field(default=None)
    should_enable_auto_orient: bool = field(default=False)
    _orientation: Optional[str] = field(default=None)
    additional_metadata: Dict = field(default=Factory(dict))

    @property
    def orientation(self) -> str:
        return (self._orientation or 'horizontal')

    @orientation.setter
    def orientation(self, value):
        self._orientation = value

    @property
    def shouldAutoOrient(self) -> bool:
        return self.should_enable_auto_orient

    @shouldAutoOrient.setter
    def shouldAutoOrient(self, value: bool):
        assert value is not None
        self.should_enable_auto_orient = value
        if self.should_enable_auto_orient:
            self.orientation = 'auto'
        else:
            pass

    def get_colors(self, orientation, is_dim):
        if is_dim:
            fg_color = '#aaa'
            bg_color = '#44a'
            border_color = '#339'
        else:
            fg_color = '#fff'
            bg_color = '#66c'
            border_color = '#55B'
        return fg_color, bg_color, border_color

    def get_stylesheet(self, orientation, is_dim):
        fg_color, bg_color, border_color = self.get_colors(orientation, is_dim)
        if orientation == 'vertical':
            return """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: 0px;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: %s;
                border-width: 0px;
                border-right: 2px solid %s;
                padding-top: 0px;
                padding-bottom: 1px;
                font-size: %s;
            }""" % (bg_color, fg_color, self.corner_radius, self.corner_radius, border_color, self.fontSize)
        else:
            return """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: %s;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-width: 0px;
                border-bottom: 2px solid %s;
                padding-left: 3px;
                padding-right: 3px;
                font-size: %s;
            }""" % (bg_color, fg_color, self.corner_radius, self.corner_radius, border_color, self.fontSize)
