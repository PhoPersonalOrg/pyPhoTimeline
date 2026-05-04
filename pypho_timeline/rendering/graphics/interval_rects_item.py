"""
IntervalRectsItem - GraphicsObject for rendering time intervals as rectangles in pyqtgraph.

Based on pyqtgraph's CandlestickItem example, adapted for pypho_timeline.
"""
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
from functools import partial
from datetime import datetime
import pandas as pd
import numpy as np
from pypho_timeline.utils.mixins import UnpackableMixin
from attrs import define, field
from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph.graphicsItems.LegendItem import ItemSample, LegendItem

from pypho_timeline.rendering.graphics.rectangle_helpers import RectangleRenderTupleHelpers
from pypho_timeline.utils.datetime_helpers import format_seconds_as_hhmmss, unix_timestamp_to_datetime

from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log

logger = get_rendering_logger(__name__)


# Optional mixins - handle with try/except
try:
    from pypho_timeline._embed.repr_printable_mixin import ReprPrintableItemMixin
except ImportError:
    # Fallback: create minimal stub if mixin not available
    class ReprPrintableItemMixin:
        pass

# Optional text item - handle with try/except
try:
    from pypho_timeline._embed.AlignableTextItem import CustomRectBoundedTextItem

except ImportError:
    # Fallback: create minimal stub if not available
    class CustomRectBoundedTextItem:
        def __init__(self, rect=None, text="", parent=None):
            pass
        def updatePosition(self):
            pass
        def setParentItem(self, parent):
            pass


@define(slots=False, repr=True)
class IntervalRectsItemData(UnpackableMixin):
    """Data class for rectangle specifications in IntervalRectsItem.
    
    Incremental progress towards more flexible self.data for `IntervalRectsItem` while maintaining 
    drop-in compatibility with pre 2025-12-10 tuple-based approach via `UnpackableMixin`.
    
    Usage:
        from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItemData
        
        rect_data_tuple: IntervalRectsItemData = IntervalRectsItemData(*rect_data_tuple)  # init from raw tuple object
        start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple  # unpack just like tuple
    """
    start_t: float = field()
    series_vertical_offset: float = field()
    duration_t: float = field()
    series_height: float = field()
    pen: QtGui.QPen = field()
    brush: QtGui.QBrush = field()
    label: Optional[str] = field(default=None)

    def UnpackableMixin_unpacking_includes(self) -> Optional[List]:
        """Items to be included (allowlist) from unpacking."""
        return [self.__attrs_attrs__.start_t, self.__attrs_attrs__.series_vertical_offset, 
                self.__attrs_attrs__.duration_t, self.__attrs_attrs__.series_height, 
                self.__attrs_attrs__.pen, self.__attrs_attrs__.brush]


class IntervalRectsItem(ReprPrintableItemMixin, pg.GraphicsObject):
    """GraphicsObject that renders 2D intervals as rectangles in a pyqtgraph plot.
    
    Based on pyqtgraph's CandlestickItem example.
    
    Rectangle Item Specification: 
        Renders rectangles, with each specified by a tuple of the form:
            (start_t, series_vertical_offset, duration_t, series_height, pen, brush)

        Note that this is analogous to the position arguments of `QRectF`:
            (left, top, width, height) and (pen, brush)
            
    Usage:
        Example 1 (basic):
            from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem
            active_interval_rects_item = IntervalRectsItem(data)
            
            ## Add the active_interval_rects_item to the main_plot_widget: 
            main_plot_widget.addItem(active_interval_rects_item)

            ## Remove the active_interval_rects_item:
            main_plot_widget.removeItem(active_interval_rects_item)

        Example 2 (with custom tooltip function; use format_seconds_as_hhmmss for HH:mm:ss):
            def _custom_format_tooltip_for_rect_data(rect_index: int, rect_data_tuple: Tuple) -> str:
                start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple
                ## get the optional label field if `rect_data_tuple` is a `IntervalRectsItemData` instead of a plain tuple
                a_label = None
                if not isinstance(rect_data_tuple, Tuple):
                    a_label = rect_data_tuple.label
                from pypho_timeline.utils.datetime_helpers import format_seconds_as_hhmmss
                end_t = start_t + duration_t
                start_s, end_s, duration_s = format_seconds_as_hhmmss(start_t), format_seconds_as_hhmmss(end_t), format_seconds_as_hhmmss(duration_t)
                if a_label:
                    tooltip_text = f"{a_label}\nItem[{rect_index}]\nStart: {start_s}\nEnd: {end_s}\nDuration: {duration_s}"
                else:
                    tooltip_text = f"Item[{rect_index}]\nStart: {start_s}\nEnd: {end_s}\nDuration: {duration_s}"
                return tooltip_text

            # Build the rendered interval item:
            from copy import deepcopy
            new_interval_rects_item = IntervalRectsItem(data, format_tooltip_fn=deepcopy(_custom_format_tooltip_for_rect_data))
    """
    pressed = False
    clickable = True
    hoverEnter = QtCore.Signal()
    hoverExit = QtCore.Signal()
    clicked = QtCore.Signal()
    ## data must have fields: start_t, series_vertical_offset, duration_t, series_height, pen, brush

    def __init__(self, data, format_tooltip_fn=None, format_label_fn=None, debug_print=False, detail_render_callback=None, extra_menu_callbacks_dict: Optional[Dict[str, Callable[[int, float], Any]]] = None, label_layout: str = "top_center"):
        # menu creation is deferred because it is expensive and often
        # the user will never see the menu anyway.
        self.menu = None
        # note that the use of super() is often avoided because Qt does not 
        # allow to inherit from multiple QObject subclasses.
        pg.GraphicsObject.__init__(self)
        self.data = data  ## data must have fields: start_t, series_vertical_offset, duration_t, series_height, pen, brush
        self.generatePicture()
        self.setAcceptHoverEvents(True)
        # Note: In pyqtgraph, overriding mousePressEvent should be sufficient for mouse events
        # Mouse events are typically accepted by default when event handlers are overridden
        self._current_hovered_rect = None  # Track which rectangle is currently hovered
        self._current_hovered_item_tooltip_format_fn = None
        if format_tooltip_fn is None:
            format_tooltip_fn = self._default_format_tooltip_for_rect_data
        if format_label_fn is None:
            # format_label_fn = self._default_format_tooltip_for_rect_data            
            pass ## no labels when not explicitly set

        self._current_hovered_item_tooltip_format_fn = format_tooltip_fn
        self._item_label_format_fn = format_label_fn
        self._label_layout = label_layout
        self._detail_render_callback = detail_render_callback  # Callback for detailed rendering: (rect_index: int, rect_data: IntervalRectsItemData) -> None
        if extra_menu_callbacks_dict is None:
            extra_menu_callbacks_dict = {}
        _default_extra_menu_callbacks = {"Turn green": partial(self._recolor_all_intervals, 'g'), "Turn blue": partial(self._recolor_all_intervals, 'b')}
        self._extra_menu_callbacks_dict = {**extra_menu_callbacks_dict, **_default_extra_menu_callbacks}

        self._labels = []
        self.rebuild_label_items()


    def generatePicture(self):
        ## pre-computing a QPicture object allows paint() to run much more quickly, 
        ## rather than re-drawing the shapes every time.
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        
        # White background bars:
        p.setPen(pg.mkPen('w'))
        p.setBrush(pg.mkBrush('r'))
        
        for rect_data in self.data:
            # Handle both tuples and IntervalRectsItemData objects
            if isinstance(rect_data, IntervalRectsItemData):
                start_t = rect_data.start_t
                series_vertical_offset = rect_data.series_vertical_offset
                duration_t = rect_data.duration_t
                series_height = rect_data.series_height
                pen = rect_data.pen
                brush = rect_data.brush
            else:
                # Tuple unpacking (backward compatibility)
                (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data
            
            # Ensure start_t is numeric for Qt rendering
            if isinstance(start_t, (datetime, pd.Timestamp)):
                from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                start_t = datetime_to_unix_timestamp(start_t)
            
            p.setPen(pen)
            p.setBrush(brush) # filling of the rectangles by a passed color:
            p.drawRect(QtCore.QRectF(start_t, series_vertical_offset, duration_t, series_height)) # QRectF: (left, top, width, height)

        p.end()
    

    def update_data(self, new_data):
        """Update the data in-place and regenerate the picture
        
        Args:
            new_data: List of tuples or IntervalRectsItemData objects with format:
                (start_t, series_vertical_offset, duration_t, series_height, pen, brush) or
                IntervalRectsItemData(...)
        """
        self.data = new_data
        self.generatePicture()
        self.update()
        # Rebuild labels if label format function exists
        if self.item_label_format_fn is not None:
            self.rebuild_label_items()
    

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)
    

    def boundingRect(self):
        ## boundingRect _must_ indicate the entire area that will be drawn on
        ## or else we will get artifacts and possibly crashing.
        ## (in this case, QPicture does all the work of computing the bounding rect for us)
        return QtCore.QRectF(self.picture.boundingRect())
    

    def shape(self):
        """Return the shape of the item for hit testing.
        
        This method is used by pyqtgraph to determine if mouse events should be sent to this item.
        We return a QPainterPath that includes all the rectangles.
        """
        path = QtGui.QPainterPath()
        for rect_data in self.data:
            # Handle both tuples and IntervalRectsItemData objects
            if isinstance(rect_data, IntervalRectsItemData):
                start_t = rect_data.start_t
                series_vertical_offset = rect_data.series_vertical_offset
                duration_t = rect_data.duration_t
                series_height = rect_data.series_height
            else:
                # Tuple unpacking (backward compatibility)
                (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data
            
            # Ensure start_t is numeric for Qt rendering
            if isinstance(start_t, (datetime, pd.Timestamp)):
                from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                start_t = datetime_to_unix_timestamp(start_t)
            
            rect = QtCore.QRectF(start_t, series_vertical_offset, duration_t, series_height)
            path.addRect(rect)
        return path


    @property
    def format_item_tooltip_fn(self) -> Callable:
        """The format_item_tooltip_fn property."""
        return self._current_hovered_item_tooltip_format_fn
    @format_item_tooltip_fn.setter
    def format_item_tooltip_fn(self, value: Callable):
        is_changing: bool = (self._current_hovered_item_tooltip_format_fn != value)
        self._current_hovered_item_tooltip_format_fn = value


    @property
    def item_label_format_fn(self):
        """The item_label_format_fn property."""
        return self._item_label_format_fn
    @item_label_format_fn.setter
    def item_label_format_fn(self, value):
        is_changing: bool = (self._item_label_format_fn != value)
        self._item_label_format_fn = value
        if is_changing:
            self.rebuild_label_items()


    def rebuild_label_items(self, debug_print: bool=False):
        """Rebuilds self._labels after update."""
        if debug_print:
            print(f'IntervalRectsItem.rebuild_label_items(...): removing existing label items: len(self._labels): {len(self._labels)}')
        ## remove existing label items:
        for a_text_item in self._labels:
            # Properly remove from parent/scene
            a_text_item.setParentItem(None)
        self._labels = []
        if debug_print:
            print(f'\tdone.')

        if self.item_label_format_fn is not None:
            if debug_print:
                print(f'\tbuilding labels...')
            ## Build labels
            empty_label_count: int = 0
            for rect_index in np.arange(len(self.data)):
                rect_data_tuple = self.data[rect_index]
                # Handle both tuples and IntervalRectsItemData objects
                if isinstance(rect_data_tuple, IntervalRectsItemData):
                    start_t = rect_data_tuple.start_t
                    series_vertical_offset = rect_data_tuple.series_vertical_offset
                    duration_t = rect_data_tuple.duration_t
                    series_height = rect_data_tuple.series_height
                    pen = rect_data_tuple.pen
                    brush = rect_data_tuple.brush
                else:
                    # Tuple unpacking (backward compatibility)
                    (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data_tuple
                label_text: str = self.item_label_format_fn(rect_index=rect_index, rect_data_tuple=rect_data_tuple)
                if label_text is None or str(label_text).strip() == '':
                    empty_label_count += 1
                a_rect = QtCore.QRectF(start_t, series_vertical_offset, duration_t, series_height)  # QRectF: (left, top, width, height)
                if debug_print:
                    print(f'rect_index: {rect_index}, a_rect: {a_rect}, label_text: "{label_text}"')
                a_text_item: CustomRectBoundedTextItem = CustomRectBoundedTextItem(rect=a_rect, text=label_text, parent=self, layout_mode=self._label_layout)

                self._labels.append(a_text_item)
                if debug_print:
                    print(f'\tadded label: {a_text_item}')
                a_text_item.updatePosition()
            n_total: int = int(len(self.data))
            if (n_total > 0) and (empty_label_count == n_total):
                logger.warning(f'IntervalRectsItem.rebuild_label_items: built {n_total} labels but ALL were empty (formatter returned no text); labels will not be visible.')
            elif empty_label_count > 0:
                logger.debug(f'IntervalRectsItem.rebuild_label_items: built {n_total} labels, {empty_label_count} empty.')
            else:
                logger.debug(f'IntervalRectsItem.rebuild_label_items: built {n_total} labels (all populated).')

        else:
            if debug_print:
                print(f'\tno self.item_label_format_fn, so not building labels.')

        if debug_print:
            print(f'\tdone.')


    ## Copy Constructors:
    def __copy__(self):
        independent_data_copy = RectangleRenderTupleHelpers.copy_data(self.data)
        return IntervalRectsItem(independent_data_copy)
    

    def __deepcopy__(self, memo):
        independent_data_copy = RectangleRenderTupleHelpers.copy_data(self.data)
        return IntervalRectsItem(independent_data_copy)

    # ==================================================================================================================== #
    # Events
    # ====================================================================================================================

    def hoverEnterEvent(self, event):
        if self.clickable:
            self.hoverEnter.emit()


    def hoverMoveEvent(self, event):
        """Handle hover move events to show tooltips for individual rectangles."""
        if not self.clickable:
            return
            
        # Get the position in item coordinates
        pos = event.pos()
        
        # Find which rectangle (if any) contains this position
        hovered_rect_index = self._get_rect_at_position(pos)
        
        if hovered_rect_index != self._current_hovered_rect:
            self._current_hovered_rect = hovered_rect_index
            
            if hovered_rect_index is not None:
                # Show tooltip for this rectangle
                global_pos = event.screenPos()
                self._show_tooltip_for_rect(hovered_rect_index, QtCore.QPoint(int(global_pos.x()), int(global_pos.y())))
            else:
                # Hide tooltip when not over any rectangle
                QtWidgets.QToolTip.hideText()


    def hoverLeaveEvent(self, event):
        if self.clickable:
            self.hoverExit.emit()
            # Hide tooltip when leaving the item
            QtWidgets.QToolTip.hideText()
            self._current_hovered_rect = None


    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            event.ignore()
            return
        if self.clickable:
            # Handle right-click for context menu
            if event.button() == QtCore.Qt.MouseButton.RightButton:
                logger.debug(f'IntervalRectsItem.mousePressEvent - right button pressed at {event.pos()}')
                # Store the clicked position to identify which rectangle was clicked
                self._context_menu_event_pos = event.pos()
                if self.raiseContextMenu(event):
                    event.accept()
                    return
            # For left-click, just track that it was pressed
            self.pressed = True


    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            event.ignore()
            return
        if self.clickable:
            pressed = False
            self.clicked.emit()

    # ==================================================================================================================== #
    # Hover Event Handlers
    # ====================================================================================================================
    def _get_rect_at_position(self, pos):
        """
        Find which rectangle (if any) contains the given position.
        Returns the index of the rectangle, or None if no rectangle contains the position.
        
        Args:
            pos: QtCore.QPointF in item coordinates
            
        Returns:
            int or None: Index of the rectangle containing the position, or None
        """
        for i, rect_data in enumerate(self.data):
            # Handle both tuples and IntervalRectsItemData objects
            if isinstance(rect_data, IntervalRectsItemData):
                start_t = rect_data.start_t
                series_vertical_offset = rect_data.series_vertical_offset
                duration_t = rect_data.duration_t
                series_height = rect_data.series_height
            else:
                # Tuple unpacking (backward compatibility)
                (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data
            rect = QtCore.QRectF(start_t, series_vertical_offset, duration_t, series_height)
            if rect.contains(pos):
                return i
        return None
    

    @classmethod
    def _default_format_tooltip_for_rect_data(cls, rect_index: int, rect_data_tuple: Tuple, datetime_tooltip_format: str='%Y-%m-%d %H:%M:%S') -> str:
        """Default tooltip formatter for rectangle data.
        
        rect_data_tuple = self.data[rect_index]
        start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple
        """
        # Handle both tuples and IntervalRectsItemData objects
        if isinstance(rect_data_tuple, IntervalRectsItemData):
            start_t = rect_data_tuple.start_t
            series_vertical_offset = rect_data_tuple.series_vertical_offset
            duration_t = rect_data_tuple.duration_t
            series_height = rect_data_tuple.series_height
            pen = rect_data_tuple.pen
            brush = rect_data_tuple.brush
            a_label = rect_data_tuple.label
        else:
            # Tuple unpacking (backward compatibility)
            start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple
            a_label = None
        
        end_t = start_t + duration_t

        ## get the start/end as datetimes and the duration as a human-readible HH:mm:ss
        start_t = unix_timestamp_to_datetime(start_t)
        end_t = unix_timestamp_to_datetime(end_t)
        # Use a short ISO format for datetime display: "YYYY-MM-DD HH:MM:SS"
        start_s: str = start_t.strftime('%Y-%m-%d %H:%M:%S')
        end_s: str = end_t.strftime('%Y-%m-%d %H:%M:%S')
        
        duration_s: str = format_seconds_as_hhmmss(duration_t)

        if a_label:
            #  tooltip_text = f"{a_label}\nItem[{rect_index}]\nStart: {start_t:.3f}\nEnd: {end_t:.3f}\nDuration: {duration_t:.3f}"
            tooltip_text = f"{a_label}\nItem[{rect_index}]\nStart: {start_s}\nEnd: {end_s}\nDuration: {duration_s}"
        else:
            # tooltip_text = f"Item[{rect_index}]\nStart: {start_s}\nEnd: {end_s}\nDuration: {duration_s}"
            tooltip_text = f"Item[{rect_index}]\nStart: {start_s}\nEnd: {end_s}\nDuration: {duration_s}"
        return tooltip_text





    def _show_tooltip_for_rect(self, rect_index, global_pos):
        """
        Show tooltip for the specified rectangle.
        
        Args:
            rect_index: Index of the rectangle in self.data
            global_pos: Global screen position for tooltip
        """
        if rect_index is None or rect_index >= len(self.data):
            return
        rect_data_tuple = self.data[rect_index]
        assert self._current_hovered_item_tooltip_format_fn is not None, f"self._current_hovered_item_tooltip_format_fn is None!"
        try:
            tooltip_text: str = self._current_hovered_item_tooltip_format_fn(rect_index=rect_index, rect_data_tuple=rect_data_tuple)
            QtWidgets.QToolTip.showText(global_pos, tooltip_text)
        except Exception as e:
            logger.exception("Tooltip formatter failed for rect_index=%s", rect_index)
            QtWidgets.QToolTip.showText(global_pos, f"Tooltip error: {e}")

    def setToolTip(self, text):
        """
        Override setToolTip to provide custom behavior.
        
        Args:
            text: Tooltip text. If None or empty, enables per-rectangle tooltips.
                  If provided, shows this static text for the entire item.
        """
        print(f'WARNING: IntervalRectsItem.setTooltip(text: "{text}") was called, but this would set a single, static tooltip for the entire graphics item and is very unlikely to be what you want to do!')
        raise NotImplementedError(f'WARNING: IntervalRectsItem.setTooltip(text: "{text}") was called, but this would set a single, static tooltip for the entire graphics item and is very unlikely to be what you want to do!')

    # ==================================================================================================================== #
    # Context Menu and Interaction Handling
    # ====================================================================================================================
    def mouseShape(self):
        """
        Return a QPainterPath representing the clickable shape of the curve
        """
        if self._mouseShape is None:
            view = self.getViewBox()
            if view is None:
                return QtGui.QPainterPath()
            stroker = QtGui.QPainterPathStroker()
            path = self.getPath()
            path = self.mapToItem(view, path)
            stroker.setWidth(self.opts['mouseWidth'])
            mousePath = stroker.createStroke(path)
            self._mouseShape = self.mapFromItem(view, mousePath)
        return self._mouseShape

    def raiseContextMenu(self, ev):
        """Works to spawn the context menu in the appropriate location."""
        logger.debug(f'IntervalRectsItem.raiseContextMenu(ev: {ev})')
        menu = self.getContextMenus(ev)
        
        # Check if menu has any actions
        if menu is None or menu.isEmpty():
            logger.debug(f'IntervalRectsItem.raiseContextMenu - menu is empty or None')
            return False
        
        # Get screen position for menu popup
        # Try multiple methods to get the global position
        pos = None
        if hasattr(ev, 'screenPos'):
            pos = ev.screenPos()
        elif hasattr(ev, 'globalPos'):
            pos = ev.globalPos()
        else:
            # Try to get from scene position
            scene_pos = ev.scenePos() if hasattr(ev, 'scenePos') else ev.pos()
            view = self.getViewBox()
            if view is not None:
                # Get the view widget to convert to global coordinates
                view_widget = view.parent()
                if view_widget is not None:
                    try:
                        # Convert scene position to global screen coordinates
                        global_pos = view_widget.mapToGlobal(view_widget.mapFromScene(scene_pos))
                        pos = global_pos
                    except Exception as e:
                        logger.debug(f'IntervalRectsItem.raiseContextMenu - error converting position: {e}')
                        pos = scene_pos
                else:
                    pos = scene_pos
            else:
                pos = scene_pos
        
        if pos is not None:
            try:
                menu.popup(QtCore.QPoint(int(pos.x()), int(pos.y())))
                logger.debug(f'IntervalRectsItem.raiseContextMenu - menu popped up at ({pos.x()}, {pos.y()})')
                return True
            except Exception as e:
                logger.error(f'IntervalRectsItem.raiseContextMenu - error showing menu: {e}', exc_info=True)
                return False
        else:
            logger.warning(f'IntervalRectsItem.raiseContextMenu - could not determine screen position')
            return False

    def getContextMenus(self, event=None):
        """Builds the context menus as needed."""
        if self.menu is None:
            self.menu = QtWidgets.QMenu()
            self.menu.setTitle("IntervalRectItem options..")
            
            # Add "Render detailed" action if callback is provided
            if self._detail_render_callback is not None:
                render_detailed = QtGui.QAction("Render detailed", self.menu)
                render_detailed.triggered.connect(self._on_render_detailed)
                self.menu.addAction(render_detailed)
                self.menu.render_detailed = render_detailed

            ## extra actions
            self.menu.extra_actions = {}
            for menu_lbl, callback_fn in self._extra_menu_callbacks_dict.items():
                an_action = QtGui.QAction(menu_lbl, self.menu)
                an_action.triggered.connect(partial(self._on_custom_menu_item_executed, callback_fn))
                self.menu.addAction(an_action)
                self.menu.extra_actions[menu_lbl] = an_action

            alpha = QtWidgets.QWidgetAction(self.menu)
            alphaSlider = QtWidgets.QSlider()
            alphaSlider.setOrientation(QtCore.Qt.Orientation.Horizontal)
            alphaSlider.setMaximum(255)
            alphaSlider.setValue(255)
            alphaSlider.valueChanged.connect(self.setAlpha)
            alpha.setDefaultWidget(alphaSlider)
            self.menu.addAction(alpha)
            self.menu.alpha = alpha
            self.menu.alphaSlider = alphaSlider
        return self.menu


    def _recolor_all_intervals(self, color_key: str, rect_index: int, click_t: float) -> None:
        override_pen = pg.mkPen(color_key)
        override_brush = pg.mkBrush(color_key)
        for i, rect_data in enumerate(self.data):
            # Handle both tuples and IntervalRectsItemData objects
            if isinstance(rect_data, IntervalRectsItemData):
                start_t = rect_data.start_t
                series_vertical_offset = rect_data.series_vertical_offset
                duration_t = rect_data.duration_t
                series_height = rect_data.series_height
                a_label = rect_data.label
            else:
                # Tuple unpacking (backward compatibility)
                (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data
                a_label = None
            override_pen = pg.mkPen('g')
            override_brush = pg.mkBrush('g')
            self.data[i] = IntervalRectsItemData(start_t, series_vertical_offset, duration_t, series_height, override_pen, override_brush, label=a_label)
        
        # Need to regenerate picture
        self.generatePicture()
        # inform Qt that this item must be redrawn.
        self.update()


    def setAlpha(self, a):
        self.setOpacity(a/255.)


    def _on_custom_menu_item_executed(self, callback_fn, checked=False):
        """Resolve rect_idx and click_t from the stored context-menu position, then call callback_fn(rect_index, click_t). The checked arg absorbs QAction.triggered(bool)."""
        if not hasattr(self, '_context_menu_event_pos'):
            logger.debug("IntervalRectsItem._on_custom_menu_item_executed - no stored context menu position")
            return
        rect_index = self._get_rect_at_position(self._context_menu_event_pos)
        if rect_index is None or rect_index >= len(self.data):
            logger.debug("IntervalRectsItem._on_custom_menu_item_executed - no rectangle at click position")
            return
        click_t = float(self._context_menu_event_pos.x())
        try:
            callback_fn(rect_index, click_t)
        except Exception as e:
            logger.error(f"IntervalRectsItem._on_custom_menu_item_executed - error in extra menu callback: {e}", exc_info=True)



    def _on_render_detailed(self):
        """Handle the 'Render detailed' context menu action."""
        assert self._detail_render_callback is not None
        
        # Get the clicked rectangle index from the stored event position
        if hasattr(self, '_context_menu_event_pos'):
            rect_index = self._get_rect_at_position(self._context_menu_event_pos)
            if rect_index is not None and rect_index < len(self.data):
                rect_data = self.data[rect_index]
                # Convert tuple to IntervalRectsItemData if needed
                if not isinstance(rect_data, IntervalRectsItemData):
                    (start_t, series_vertical_offset, duration_t, series_height, pen, brush) = rect_data
                    rect_data = IntervalRectsItemData(start_t, series_vertical_offset, duration_t, series_height, pen, brush)
                # Call the callback
                try:
                    self._detail_render_callback(rect_index, rect_data)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error in detail_render_callback: {e}", exc_info=True)


class CustomLegendItemSample(ReprPrintableItemMixin, ItemSample):
    """An ItemSample that can render a legend item for `IntervalRectsItem`
    
    Usage:
        from pypho_timeline.rendering.graphics.interval_rects_item import CustomLegendItemSample
        
        legend = pg.LegendItem(offset=(-10, -10))
        legend.setParentItem(plt.graphicsItem())
        legend.setSampleType(CustomLegendItemSample)
    """
    def __init__(self, item):
        super().__init__(item)
        self.item = item

    def paint(self, p, *args):
        if not isinstance(self.item, IntervalRectsItem):
            ## Call superclass paint
            super().paint(p, *args)
        else:
            # Custom Implementation
            if not self.item.isVisible():
                p.setPen(pg.mkPen('w'))
                p.drawLine(0, 11, 20, 11) # draw flat white line
                return

            # Define the size of the rectangle
            rect_width = 20
            rect_height = 8

            # Calculate the top-left corner coordinates to center the rectangle
            top_left_x = (self.boundingRect().width() - rect_width) / 2
            top_left_y = (self.boundingRect().height() - rect_height) / 2

            # The first item is representative of all items, don't draw the item over-and-over
            use_only_first_items: bool = True

            for rect_data in self.item.data:
                # Handle both tuples and IntervalRectsItemData objects
                if isinstance(rect_data, IntervalRectsItemData):
                    pen = rect_data.pen
                    brush = rect_data.brush
                else:
                    # Tuple unpacking (backward compatibility)
                    pen, brush = rect_data[4], rect_data[5]
                if (pen is not None) or (brush is not None):                   
                    p.setPen(pen)
                    p.setBrush(brush)
                    p.drawRect(QtCore.QRectF(top_left_x, top_left_y, rect_width, rect_height))
                    if use_only_first_items:
                        return # break, only needed to draw one item

