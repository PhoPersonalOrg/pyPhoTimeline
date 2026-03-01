from typing import Callable, Optional, Dict, List, Tuple, Union
from collections import OrderedDict
from enum import Enum
from attrs import define, field, Factory
import numpy as np

from pypho_timeline.utils.colors_util import ColorsUtil
from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph.dockarea import Dock
from pypho_timeline._embed.dock_display_config import DockDisplayConfig

# Optional imports - can be simplified if not available
try:
    from pyphoplacecellanalysis.General.Model.Configs.LongShortDisplayConfig import DisplayColorsEnum
except (ImportError, ModuleNotFoundError):
    # Fallback stub
    class DisplayColorsEnum:
        @staticmethod
        def apply_dock_border_color_adjustment(bg_color):
            return bg_color
        @staticmethod
        def apply_dock_dimming_adjustment(bg_color, fg_color=None):
            if fg_color is None:
                return bg_color
            return bg_color, fg_color


@define(slots=False)
class DockDisplayColors:
    """ 
    Usage:
    
        from pypho_timeline.docking.dock_display_configs import DockDisplayColors, CustomDockDisplayConfig

        dim_config = DockDisplayColors(fg_color='#aaa', bg_color='#44aa44', border_color='#339933')
        regular_config = DockDisplayColors(fg_color='#fff', bg_color='#66cc66', border_color='#54ba54')
        custom_get_colors_dict = {   False: DockDisplayColors(fg_color='#aaa', bg_color='#44aa44', border_color='#339933'),
            True: DockDisplayColors(fg_color='#fff', bg_color='#66cc66', border_color='#54ba54')
        }


    """
    fg_color: str = field(default='#aaa') # Grey
    bg_color: str = field(default='#66cc66') # (120°, 50, 80)
    border_color: str = field(default='#54ba54') # (120°, 55%, 73%)


    @classmethod
    def _subfn_get_random_dock_colors_for_key(cls, key, orientation, is_dim):
        """Generate consistent random colors for a dock based on its key."""
        try:
            from pyphoplacecellanalysis.General.Model.Configs.LongShortDisplayConfig import DisplayColorsEnum
        except (ImportError, ModuleNotFoundError):
            DisplayColorsEnum = globals()['DisplayColorsEnum']

        # Generate a unique background color based on the key
        bg_color = ColorsUtil.generate_unique_hex_color_from_hashable((key, 'bg'))
        
        # Create a darker border color based on the background color
        border_color = DisplayColorsEnum.apply_dock_border_color_adjustment(bg_color)
        
        # Choose a contrasting foreground color (white or black) based on background brightness
        # Simple algorithm: if R+G+B > 384 (out of 765 max), use black text, otherwise white
        r, g, b = int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16)
        fg_color = '#000' if (r + g + b) > 384 else '#fff'
        
        # Apply dimming if requested
        if is_dim:
            bg_color, fg_color = DisplayColorsEnum.apply_dock_dimming_adjustment(bg_color, fg_color)
            border_color = DisplayColorsEnum.apply_dock_dimming_adjustment(border_color)
        
        return fg_color, bg_color, border_color
    


    @classmethod
    def get_random_dock_colors_for_key_fn(cls, key) -> Callable:
        """Returns a valid `custom_get_colors_callback_fn` that generates consistent random colors for a dock based on its initialization-time key/identity.
        Usage:
            custom_get_colors_callback_fn = DockDisplayColors.get_random_dock_colors_for_key_fn(key=a_key)
        
        """
        from functools import partial
        custom_get_colors_callback_fn = partial(cls._subfn_get_random_dock_colors_for_key, key)
        return custom_get_colors_callback_fn




@define(slots=False)
class CustomDockDisplayConfig(DockDisplayConfig):
    """Holds the display and configuration options for a Dock, such as how to format its title bar (color and font), whether it's closable, etc.

    custom_get_colors_callback, if provided, is used to get the colors. This function must be of the form:
        get_colors(self, orientation, is_dim) -> return fg_color, bg_color, border_color
    """
    custom_get_colors_dict: Optional[Dict] = field(default=None)
    _custom_get_colors_callback_fn: Optional[Callable] = field(default=None, alias='custom_get_colors_callback_fn')
    dock_group_names: List[str] = field(default=Factory(list), metadata={'desc': 'a list of conceptual "groups" that the dock specified by this config belongs to. Allows closing, moving, etc multiple docks at a time.'})
    # additional_metadata: Dict = field(default=Factory(dict)) ## optional metadata
    

    @property
    def custom_get_colors_callback(self):
        """The custom_get_colors_callback property."""
        return self._custom_get_colors_callback_fn
    @custom_get_colors_callback.setter
    def custom_get_colors_callback(self, value):
        self._custom_get_colors_callback_fn = value


    @property
    def orientation(self) -> str:
        """The orientation property."""
        return (self._orientation or 'auto' )   
    @orientation.setter
    def orientation(self, value):
        self._orientation = value

    def __attrs_post_init__(self):
      if self.custom_get_colors_dict is None:
            self.custom_get_colors_dict = {False: DockDisplayColors(fg_color='#111', bg_color='#66cc66', border_color='#54ba54'),
                True: DockDisplayColors(fg_color='#333', bg_color='#44aa44', border_color='#339933'),
            }

        

    def get_colors(self, orientation, is_dim):
        if self.custom_get_colors_callback is not None:
            # Use the custom function instead
            return self.custom_get_colors_callback(orientation, is_dim)

        else:
            if self.custom_get_colors_dict is not None:
                ## otherwise use the `self.custom_get_colors_dict`
                active_colors_dict = self.custom_get_colors_dict[is_dim]
                fg_color = active_colors_dict.fg_color
                bg_color = active_colors_dict.bg_color
                border_color = active_colors_dict.border_color      

            else:
                # Common to all:
                if is_dim:
                    fg_color = '#aaa' # Grey
                else:
                    fg_color = '#fff' # White
                
                # Green-based:
                if is_dim:
                    bg_color = '#44aa44' # (120°, 60%, 67%)
                    border_color = '#339933' # (120°, 67%, 60%)
                else:
                    bg_color = '#66cc66' # (120°, 50, 80)
                    border_color = '#54ba54' # (120°, 55%, 73%)
    
            return fg_color, bg_color, border_color
    
    @classmethod
    def build_custom_get_colors_fn(cls, bg_color: str = '#44aa44', border_color: str = '#339933', fg_color: str = '#aaa'):
            """ Builds the custom callback function from some colors:
            
            self.custom_get_colors_callback = CustomDockDisplayConfig.build_custom_get_colors_fn(bg_color='#44aa44', border_color='#339933')
            
            """
            def _subfn_custom_get_colors(self, orientation, is_dim):
                """ captures: bg_color, border_color, fg_color 
                """
                if self.custom_get_colors_callback is not None:
                    # Use the custom function instead
                    return self.custom_get_colors_callback(orientation, is_dim)

                else:
                    # Common to all:
                    if is_dim:
                        fg_color = fg_color or '#aaa' # Grey
                    else:
                        fg_color = fg_color or '#fff' # White
                    
                    # Green-based by default, but custom-color if provided:
                    if is_dim:
                        bg_color = bg_color or '#44aa44' # (120°, 60%, 67%)
                        border_color = border_color or '#339933' # (120°, 67%, 60%)
                    else:
                        bg_color = bg_color or '#66cc66' # (120°, 50, 80)
                        border_color = border_color or '#54ba54' # (120°, 55%, 73%)
                        
                    return fg_color, bg_color, border_color

            ## end def _subfn_custom_get_colors(...)
            return _subfn_custom_get_colors
    


## Build Dock Widgets:
def get_utility_dock_colors(orientation, is_dim):
    """ used for CustomDockDisplayConfig for non-specialized utility docks """
    # Common to all:
    if is_dim:
        fg_color = '#aaa' # Grey
    else:
        fg_color = '#fff' # White
        
    # a purplish-royal-blue 
    if is_dim:
        bg_color = '#d8d8d8' 
        border_color = '#717171' 
    else:
        bg_color = '#9d9d9d' 
        border_color = '#3a3a3a' 

    return fg_color, bg_color, border_color

    
NamedColorScheme = Enum('NamedColorScheme', 'blue green red grey')
# NamedColorScheme.blue  # returns <Animal.ant: 1>
# NamedColorScheme['blue']  # returns <Animal.ant: 1> (string lookup)
# NamedColorScheme.blue.name  # returns 'ant' (inverse lookup)

@define(slots=False)
class CustomCyclicColorsDockDisplayConfig(CustomDockDisplayConfig):
    """Holds the display and configuration options for a Dock, such as how to format its title bar (color and font), whether it's closable, etc.

    custom_get_colors_callback, if provided, is used to get the colors. This function must be of the form:
        get_colors(self, orientation, is_dim) -> return fg_color, bg_color, border_color
    """
    named_color_scheme: NamedColorScheme = field(default=NamedColorScheme.red, alias='named_color_scheme')

    def __attrs_post_init__(self):
      if self.custom_get_colors_dict is None:
            pass # don't update it here, default to None

    def get_colors(self, orientation, is_dim):
        if self.custom_get_colors_callback is not None:
            # Use the custom function instead
            return self.custom_get_colors_callback(orientation, is_dim)

        else:
            if self.custom_get_colors_dict is not None:
                ## otherwise use the `self.custom_get_colors_dict`
                active_colors_dict = self.custom_get_colors_dict[is_dim]
                fg_color = active_colors_dict.fg_color
                bg_color = active_colors_dict.bg_color
                border_color = active_colors_dict.border_color      

            else:
                # Common to all:
                if is_dim:
                    fg_color = '#aaa' # Grey
                else:
                    fg_color = '#fff' # White

                if self.named_color_scheme.name == NamedColorScheme.blue.name:
                    # Blue/Purple-based:
                    if is_dim:
                        bg_color = '#4444aa' # Dark Blue - (240°, 60, 66.66)
                        border_color = '#339' # More Vibrant Dark Blue - (240°, 66.66, 60)
                    else:
                        bg_color = '#6666cc' # Default Purple Color - (240°, 50, 80)
                        border_color = '#55B' # Similar Purple Color - (240°, 54.54, 73.33)
                elif self.named_color_scheme.name == NamedColorScheme.green.name:
                    # Green-based:
                    if is_dim:
                        bg_color = '#44aa44' # (120°, 60%, 67%)
                        border_color = '#339933' # (120°, 67%, 60%)
                    else:
                        bg_color = '#66cc66' # (120°, 50, 80)
                        border_color = '#54ba54' # (120°, 55%, 73%)
                elif self.named_color_scheme.name == NamedColorScheme.red.name:
                    # Red-based:
                    if is_dim:
                        bg_color = '#aa4444' # (0°, 60%, 67%)
                        border_color = '#993232' # (0°, 67%, 60%)
                    else:
                        bg_color = '#cc6666' # (0°, 50, 80)
                        border_color = '#ba5454' # (0°, 55%, 73%)
                elif self.named_color_scheme.name == NamedColorScheme.grey.name:
                    # Grey-based:
                    if is_dim:
                        bg_color = '#d8d8d8' 
                        border_color = '#717171' 
                    else:
                        bg_color = '#9d9d9d' 
                        border_color = '#3a3a3a' 
                else:
                    raise NotImplementedError
            # END else:
            return fg_color, bg_color, border_color

@define(slots=False)
class FigureWidgetDockDisplayConfig(CustomDockDisplayConfig):
    """docstring for FigureWidgetDockDisplayConfig."""

    def get_colors(self, orientation, is_dim):
        # Common to all:
        if is_dim:
            fg_color = '#aaa' # Grey
        else:
            fg_color = '#fff' # White
            
        # Red-based:
        if is_dim:
            bg_color = '#aa4444' # (0°, 60%, 67%)
            border_color = '#993232' # (0°, 67%, 60%)
        else:
            bg_color = '#cc6666' # (0°, 50, 80)
            border_color = '#ba5454' # (0°, 55%, 73%)
 
        return fg_color, bg_color, border_color
    
    def __attrs_post_init__(self):
      self.fontSize = '10px'
      self.corner_radius = '3px'
      if self.custom_get_colors_dict is None:
            self.custom_get_colors_dict = {False: DockDisplayColors(fg_color='#fff', bg_color='#cc6666', border_color='#ba5454'),
                True: DockDisplayColors(fg_color='#aaa', bg_color='#aa4444', border_color='#993232'),
            }
            


