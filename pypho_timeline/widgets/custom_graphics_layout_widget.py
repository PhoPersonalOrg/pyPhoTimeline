from typing import Callable
from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyphocorehelpers.programming_helpers import metadata_attributes
from pyphocorehelpers.function_helpers import function_attributes

# Simplified mixins - can be made optional if needed
try:
    from pypho_timeline._embed.repr_printable_mixin import ReprPrintableItemMixin
    from pypho_timeline._embed.DraggableGraphicsWidgetMixin import DraggableGraphicsWidgetMixin

except ImportError:
    # Fallback: create minimal stubs if mixins not available
    class ReprPrintableItemMixin:
        pass
    class DraggableGraphicsWidgetMixin:
        pass
    MouseInteractionCriteria = None


class CustomGraphicsLayoutWidget(ReprPrintableItemMixin, DraggableGraphicsWidgetMixin, pg.GraphicsLayoutWidget):
    """ can forward events to a child 
    
    from pypho_timeline.widgets.custom_graphics_layout_widget import CustomGraphicsLayoutWidget
    
    
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_event_handler_child = None  # The child item to forward events to

    def set_target_event_forwarding_child(self, child):
        """Set the child item to which events should be forwarded."""
        self.target_event_handler_child = child

    
    @classmethod
    def build_PlotWithCustomViewbox(cls, viewbox_kwargs=None, viewBox=None, **kargs):
        """
        Create a PlotItem and place it in the next available cell (or in the cell specified)
        All extra keyword arguments are passed to :func:`PlotItem.__init__ <pyqtgraph.PlotItem.__init__>`
        Returns the created item.

        (plot_item, vb) = CustomGraphicsLayoutWidget.build_PlotWithCustomViewbox()
        # (plot_item, vb) = CustomGraphicsLayoutWidget.build_PlotWithCustomViewbox(viewBox=vb, **kargs)
        
        """
        # vb = kargs.pop('viewBox', None)
        if viewBox is None:
            if viewbox_kwargs is None:
                viewbox_kwargs = {}
            viewBox = CustomViewBox(**viewbox_kwargs)
        plot_item = pg.PlotItem(viewBox=viewBox, **kargs)
        return (plot_item, viewBox)
    


    def addPlot(self, row=None, col=None, rowspan=1, colspan=1, **kargs):
        """
        Create a PlotItem and place it in the next available cell (or in the cell specified)
        All extra keyword arguments are passed to :func:`PlotItem.__init__ <pyqtgraph.PlotItem.__init__>`
        Returns the created item.
        """
        vb = kargs.pop('viewBox', None)
        # if vb is None:
        #     vb = CustomViewBox(**kargs)
        # plot_item = pg.PlotItem(viewBox=vb, **kargs)        
        (plot_item, vb) = CustomGraphicsLayoutWidget.build_PlotWithCustomViewbox(viewBox=vb, **kargs)
        self.addItem(plot_item, row, col, rowspan, colspan)
        return plot_item
        
    def addViewBox(self, row=None, col=None, rowspan=1, colspan=1, **kargs):
        """
        Create a ViewBox and place it in the next available cell (or in the cell specified)
        All extra keyword arguments are passed to :func:`ViewBox.__init__ <pyqtgraph.ViewBox.__init__>`
        Returns the created item.
        """
        vb = CustomViewBox(**kargs)
        self.addItem(vb, row, col, rowspan, colspan)
        return vb
                

    def addPlotWithCustomViewbox(self, row=None, col=None, rowspan=1, colspan=1, **kargs):
        """
        Create a PlotItem and place it in the next available cell (or in the cell specified)
        All extra keyword arguments are passed to :func:`PlotItem.__init__ <pyqtgraph.PlotItem.__init__>`
        Returns the created item.
        """
        vb = kargs.pop('viewBox', None)
        # if vb is None:
        #     vb = CustomViewBox()
        # plot_item = pg.PlotItem(viewBox=vb, **kargs)
        (plot_item, vb) = CustomGraphicsLayoutWidget.build_PlotWithCustomViewbox(viewBox=vb, **kargs)
        self.addItem(plot_item, row, col, rowspan, colspan)
        return (plot_item, vb)
    

    # def addLayout(self, row=None, col=None, rowspan=1, colspan=1, **kargs):
    #     """
    #     Create an empty GraphicsLayout and place it in the next available cell (or in the cell specified)
    #     All extra keyword arguments are passed to :func:`GraphicsLayout.__init__ <pyqtgraph.GraphicsLayout.__init__>`
    #     Returns the created item.
    #     """
    #     layout = pg.GraphicsLayout(**kargs)
    #     self.addItem(layout, row, col, rowspan, colspan)
    #     return layout
    

    
    # ==================================================================================================================== #
    # Events                                                                                                               #
    # ==================================================================================================================== #
    
    def mouseDragEvent(self, ev):
        print(f'CustomGraphicsLayoutWidget.mouseDragEvent(ev: {ev}') if hasattr(self, 'target_event_handler_child') and self.target_event_handler_child else None
        if self.target_event_handler_child:
            # Forward the event to the child
            self.target_event_handler_child.mouseDragEvent(ev)
        else:
            # Default behavior if no target child is set
            super().mouseDragEvent(ev)     

            
    def mouseClickEvent(self, ev):
        print(f'CustomGraphicsLayoutWidget.mouseClickEvent(ev: {ev}') if hasattr(self, 'target_event_handler_child') and self.target_event_handler_child else None
        if self.target_event_handler_child:
            # Forward the event to the child
            self.target_event_handler_child.mouseClickEvent(ev)
        else:
            # Default behavior if no target child is set
            super().mouseClickEvent(ev)     

    def hoverEvent(self, ev):
        print(f'CustomGraphicsLayoutWidget.hoverEvent(ev: {ev}') if hasattr(self, 'target_event_handler_child') and self.target_event_handler_child else None
        if self.target_event_handler_child:
            # Forward the event to the child
            self.target_event_handler_child.hoverEvent(ev)
        else:
            # Default behavior if no target child is set
            super().hoverEvent(ev)                 



@metadata_attributes(short_name=None, tags=['scroll', 'ui', 'viewbox', 'gui'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2025-01-07 01:50', related_items=[])
class CustomViewBox(ReprPrintableItemMixin, pg.ViewBox):
    """ A custom pg.ViewBox subclass that supports forwarding drag events in the plot to a specific graphic (such as a `CustomLinearRegionItem`)
    
        from pypho_timeline.widgets.custom_graphics_layout_widget import CustomViewBox
    """
    # sigLeftDrag = QtCore.Signal(object)  # optional custom signal
    sigLeftDrag = QtCore.Signal(float)

    def __init__(self, *args, **kwds):
        kwds['enableMenu'] = False
        pg.ViewBox.__init__(self, *args, **kwds)
        # self.setMouseMode(self.RectMode) # #TODO 2026-03-05 10:23: - [ ] CONFIRMED this is where the rect functionality was coming in
        self.setMouseMode(self.PanMode)
        self._debug_print = False
        self._last_drag_start_point = None
        self._last_drag_step_point = None
        

    def __repr__(self):
        out_str: str = "CustomViewBox"
        out_str_list = []
        try:
            view_range_str = f"viewRange: [[xmin, xmax], [ymin, ymax]]: {self.viewRange()}"
            out_str_list.append(view_range_str)                    
        except Exception as e:
            raise e

        if len(out_str_list) > 0:
            out_str = f"{out_str}[" + ', '.join(out_str_list) + ']'
            
        return out_str
        # return super().__repr__()


    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        # if ev.button() == QtCore.Qt.MouseButton.RightButton:
        #     ## this mode enables right-mouse clicks to reset the plot range
        #     self.autoRange()     
        if self._debug_print:      
            print(f'CustomViewBox.mouseClickEvent(ev: {ev})')
        # Custom logic
        ev.accept()  # or ev.ignore() if you want default handling
        # Optionally call super() if desired:
        # super().mousePressEvent(ev)
        
    
    ## reimplement mouseDragEvent to disable continuous axis zoom
    def mouseDragEvent(self, ev, axis=None):
        if self._debug_print:      
            print(f'CustomViewBox.mouseDragEvent(ev: {ev}, axis={axis})')

        ## Just do default mouse drag event stuff:
        super().mouseDragEvent(ev, axis=axis)
        ev.accept()

        # ev.accept()
        # if (ev.button() == QtCore.Qt.MouseButton.RightButton): # (axis is not None) and
        #     # Allow default zoom behavior for right-click drag (rectangular zoom)
        #     super().mouseDragEvent(ev, axis=axis)
        #     ev.accept()

        # elif (ev.button() == QtCore.Qt.MouseButton.LeftButton):
        #     # axis is not None and 
        #     # Emit a signal or directly update the slider here
        #     new_start_point = self.mapSceneToView(ev.pos()) # PyQt5.QtCore.QPointF
        #     new_start_t = new_start_point.x()
        #     # print(f'new_start_t: {new_start_t}')
            
        #     if self._debug_print:      
        #         print(f'\tCustomViewBox._last_drag_start_point: {self._last_drag_start_point}')
        #     if ev.isStart():
        #         if self._debug_print:      
        #             print(f'ev.isStart(): new_start_t: {new_start_t}')
        #         # bdp = ev.buttonDownPos()
        #         self._last_drag_start_point = new_start_t
        #         self._last_drag_step_point = new_start_t
        #     # if not (self._last_drag_start_point is not None):
        #     #     return
            
        #     if ev.isFinish():
        #         if self._debug_print:      
        #             print(f'ev.isFinish(): new_start_t: {new_start_t}, self._last_drag_start_point: {self._last_drag_start_point}')
        #         # self.sigRegionChangeFinished.emit(self)
        #         self._last_drag_start_point = None
        #         self._last_drag_step_point = None
        #     else:
        #         # assert self._last_drag_start_point is not None
        #         # curr_step_change: float = new_start_t - self._last_drag_start_point
        #         assert self._last_drag_step_point is not None
        #         curr_step_change: float = new_start_t - self._last_drag_step_point
        #         if self._debug_print:      
        #             print(f'curr_step_change: {curr_step_change}')
        #         if abs(curr_step_change) > 0.0:
        #             # self.sigRegionChanged.emit(self)
        #             self.sigLeftDrag.emit(curr_step_change)
                
        #         self._last_drag_step_point = new_start_t
        #         # self._last_drag_start_point = new_start_t
                
        #     # self.sigLeftDrag.emit(new_start_t)

        #     super().mouseDragEvent(ev, axis=axis) ## #TODO 2026-03-05 09:00: - [ ] Add this to hopefully enable the normal LMB + Drag to pan
        #     ev.accept()
            
        # elif (ev.button() == QtCore.Qt.MouseButton.MiddleButton): # (axis is not None) and
        #     if ev.isStart():
        #         self.setCursor(QtCore.Qt.ClosedHandCursor)  # Change cursor to indicate panning
        #         self._drag_start_pos = self.mapSceneToView(ev.buttonDownPos())
        #     elif ev.isFinish():
        #         self.setCursor(QtCore.Qt.ArrowCursor)  # Restore cursor after panning
        #     else:
        #         # Calculate the panning delta for the x-axis only
        #         current_pos = self.mapSceneToView(ev.pos())
        #         delta_x = current_pos.x() - self._drag_start_pos.x()  # Only use x-delta
        #         self._drag_start_pos.setX(current_pos.x())  # Update x start position

        #         # Adjust the view range for the x-axis only
        #         self.translateBy(x=-delta_x, y=0)  # Lock y-axis by setting y delta to 0

        #     ev.accept()

        # else:
        #     # pg.ViewBox.mouseDragEvent(self, ev, axis=axis)            
        #     # Custom dragging logic
        #     ev.accept()
        #     # super().mouseDragEvent(ev, axis=axis)  # only if you want default drag/pan
        
        
    def wheelEvent(self, ev, axis=None):
        """Handle mouse wheel events for zooming.
        
        For VideoTracks, only adjusts x-value (horizontal zoom) and locks y-values.
        For other tracks, uses pyqtgraph's default wheel zoom behavior.
        """
        if self._debug_print:
            print(f'CustomViewBox.wheelEvent(ev: {ev}, axis={axis})')
        
        # # Check if this ViewBox is associated with a VideoTrack
        # allow_zoom_x_only: bool = True
        
        # if allow_zoom_x_only:
        #     # For VideoTracks, only zoom on x-axis (lock y-axis)
        #     # Get current view range
        #     current_range = self.viewRange()
        #     x_range = current_range[0]
        #     y_range = current_range[1]
            
        #     # Get mouse position in view coordinates
        #     mouse_pos = self.mapSceneToView(ev.pos())
            
        #     # Calculate zoom factor (pyqtgraph uses 1.02 per step)
        #     delta = ev.angleDelta().y()
        #     if delta > 0:
        #         zoom_factor = 1.02
        #     else:
        #         zoom_factor = 1.0 / 1.02
            
        #     # Calculate new x range centered on mouse position
        #     x_center = mouse_pos.x()
        #     x_width = x_range[1] - x_range[0]
        #     new_x_width = x_width / zoom_factor
        #     new_x_min = x_center - (x_center - x_range[0]) * (new_x_width / x_width)
        #     new_x_max = new_x_min + new_x_width
            
        #     # Set new range (only x-axis changes, y-axis stays locked)
        #     self.setRange(xRange=(new_x_min, new_x_max), yRange=y_range, padding=0)
        # else:
        # Use default pyqtgraph wheel zoom behavior for non-video tracks
        super().wheelEvent(ev, axis=axis)
        
        ev.accept()

