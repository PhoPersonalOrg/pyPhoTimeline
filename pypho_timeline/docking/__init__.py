"""Docking functionality for timeline tracks - dock management, display configs, and track creation."""

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

__all__ = [
    'DockDisplayColors',
    'CustomDockDisplayConfig',
    'CustomCyclicColorsDockDisplayConfig',
    'FigureWidgetDockDisplayConfig',
    'NamedColorScheme',
    'DynamicDockDisplayAreaContentMixin',
    'DynamicDockDisplayAreaOwningMixin',
    'NestedDockAreaWidget',
    'SpecificDockWidgetManipulatingMixin',
]

