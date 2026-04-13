from copy import deepcopy
from typing import Optional
from datetime import datetime
import numpy as np
import pandas as pd
from qtpy import QtCore, QtWidgets

from numpy.typing import NDArray
import numpy as np
import pypho_timeline.EXTERNAL.pyqtgraph as pg
from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, create_am_pm_date_axis, unix_timestamp_to_datetime
from pyphocorehelpers.DataStructure.general_parameter_containers import VisualizationParameters, RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots
from pyphocorehelpers.DataStructure.dynamic_parameters import DynamicParameters
from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.gui.Qt.connections_container import ConnectionsContainer

from pypho_timeline.core.time_synchronized_plotter_base import TimeSynchronizedPlotterBase
from pyphocorehelpers.programming_helpers import metadata_attributes
from pyphocorehelpers.function_helpers import function_attributes
from pyphocorehelpers.plotting.mixins.plotting_backend_mixin import PlottingBackendSpecifyingMixin, PlottingBackendType, PlotImageExportableMixin
from pypho_timeline.widgets.custom_graphics_layout_widget import CustomViewBox, CustomGraphicsLayoutWidget
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot

from pypho_timeline.EXTERNAL.pyqtgraph_extensions.mixins.DraggableGraphicsWidgetMixin import MouseInteractionCriteria, DraggableGraphicsWidgetMixin

@metadata_attributes(short_name=None, tags=['pyqtgraph'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2024-12-31 03:42', related_items=['MatplotlibTimeSynchronizedWidget'])
class PyqtgraphTimeSynchronizedWidget(PlotImageExportableMixin, PlottingBackendSpecifyingMixin, TimeSynchronizedPlotterBase):
    """ Plots the decoded position at a given moment in time. 

    Simple pyqtgraph-based alternative to `MatplotlibTimeSynchronizedWidget`
    
    Usage:
        from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
        TODO: Document

    """
    # Application/Window Configuration Options:
    applicationName = 'PyqtgraphTimeSynchronizedWidgetApp'
    windowName = 'PyqtgraphTimeSynchronizedWidgetWindow'
    
    enable_debug_print = True
    
    sigCrosshairsUpdated = QtCore.Signal(object, str, str) # (self, name, trace_value) - CrosshairsTracingMixin Conformance

    @classmethod
    def get_plot_backing_type(cls) -> PlottingBackendType:
        """PlottingBackendSpecifyingMixin conformance: Implementor should return either [PlottingBackendType.Matplotlib, PlottingBackendType.PyQtGraph]."""
        return PlottingBackendType.PyQtGraph
    

    # @property
    # def time_window_centers(self):
    #     """The time_window_centers property."""
    #     return self.active_one_step_decoder.time_window_centers # get time window centers (n_time_window_centers,)
    

    # @property
    # def posterior_variable_to_render(self):
    #     """The occupancy_mode_to_render property."""
    #     return self.params.posterior_variable_to_render
    # @posterior_variable_to_render.setter
    # def posterior_variable_to_render(self, value):
    #     self.params.posterior_variable_to_render = value
    #     # on update, be sure to call self._update_plots()
    #     self._update_plots()
    
    @property
    def windowTitle(self):
        """The windowTitle property."""
        return self.params.window_title
    @windowTitle.setter
    def windowTitle(self, value):
        self.params.window_title = value
        if self.window().isVisible():
            print(f'updating the window title!!')
            self.window().setWindowTitle(self.params.window_title)

    

    @property
    def last_t(self):
        raise NotImplementedError(f'Parent property that should not be accessed!')



    @property
    def active_plot_target(self):
        """The active_plot_target property."""
        return self.getRootPlotItem()
    


    def __init__(self, name='PyqtgraphTimeSynchronizedWidget', plot_function_name=None, scrollable_figure=True, application_name=None, window_name=None, parent=None, reference_datetime: Optional[datetime] = None, **kwargs):
        """_summary_
        , disable_toolbar=True, size=(5.0, 4.0), dpi=72
        ## allows toggling between the various computed occupancies: such as raw counts,  normalized location, and seconds_occupancy
            occupancy_mode_to_render: ['seconds_occupancy', 'num_pos_samples_occupancy', 'num_pos_samples_smoothed_occupancy', 'normalized_occupancy']
        
        """
        super().__init__(application_name=application_name, window_name=(window_name or PyqtgraphTimeSynchronizedWidget.windowName), parent=parent) # Call the inherited classes __init__ method
            
        ## Init containers:
        self.params = VisualizationParameters(name=name, plot_function_name=plot_function_name, debug_print=False, wants_crosshairs=kwargs.get('wants_crosshairs', False),
                            should_force_discrete_to_bins=kwargs.get('should_force_discrete_to_bins', False),
                            plotAreaMouseInteractionCriteria=kwargs.get('plotAreaMouseInteractionCriteria', None), # #TODO 2026-03-05 09:04: - [ ] not yet used, not sure if needed
                            )
        self.plots_data = RenderPlotsData(name=name)
        self.plots = PyqtgraphRenderPlots(name=name)
        self.ui = PhoUIContainer(name=name, connections=ConnectionsContainer())
        # Initialize connections as ConnectionsContainer for consistency with rest of codebase
        if isinstance(self.ui, DynamicParameters):
            self.ui.setdefault('connections', ConnectionsContainer())
        else:
            self.ui.connections = ConnectionsContainer()

        self.params.name = name
        if plot_function_name is not None:
            self.params.window_title = f" - ".join([name, plot_function_name]) # name should be first so window title is rendered reasonably. kwargs.pop('plot_function_name', name)
        else:
            # TypeError: sequence item 1: expected str instance, NoneType found
            self.params.window_title = f"{name}"
            
        self.params.scrollable_figure = scrollable_figure
        self.params.scrollAreaContents_MinimumHeight = kwargs.pop('scrollAreaContents_MinimumHeight', None)
        self.params.verticalScrollBarPolicy = kwargs.pop('verticalScrollBarPolicy', pg.QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.params.horizontalScrollBarPolicy = kwargs.pop('horizontalScrollBarPolicy', pg.QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Reference datetime for datetime axis alignment (set before setup/buildUI so _buildGraphics can access it)
        self.reference_datetime = reference_datetime
        
        # self.last_window_index = None
        # self.last_window_time = None
        self.setup()
        

        #TODO 2026-03-05 08:52: - [ ] Build the mouse criteria to determine which drags are allowed (hopefully allowing left-click drag)
        #### This code came from `pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.GraphicsObjects.CustomLinearRegionItem.CustomLinearRegionItem`, get the rest there when needed.
        ## Setup the mouse action critiera for the background rectangle (excluding the two end-position lines, which are set below):
        if self.params.plotAreaMouseInteractionCriteria is None:
            # Original/Default Conditions
            self.params.plotAreaMouseInteractionCriteria = MouseInteractionCriteria(drag=lambda an_evt: (an_evt.button() == QtCore.Qt.MouseButton.LeftButton),
                                                                        hover=lambda an_evt: (an_evt.acceptDrags(QtCore.Qt.MouseButton.LeftButton)),
                                                                        click=lambda an_evt: (an_evt.button() == QtCore.Qt.MouseButton.RightButton) ## allow right-clicking
            )
            
            # Actually override drag:
            def _override_accept_either_mouse_button_drags(an_evt):
                can_accept = an_evt.acceptDrags(QtCore.Qt.MouseButton.LeftButton)
                can_accept = can_accept and an_evt.acceptDrags(QtCore.Qt.MouseButton.MiddleButton)
                return can_accept
            self.params.plotAreaMouseInteractionCriteria.hover = _override_accept_either_mouse_button_drags
            
            self.params.plotAreaMouseInteractionCriteria.drag = lambda an_evt: (an_evt.button() == QtCore.Qt.MouseButton.LeftButton) or (an_evt.button() == QtCore.Qt.MouseButton.MiddleButton)
            
            
        self._custom_area_mouse_action_criteria = self.params.plotAreaMouseInteractionCriteria


        self.buildUI()
        # self.TrackOptionsPanelOwningMixin_on_buildUI()
        
        self._update_plots()
        
        # Track renderer reference for options panel (set when track is added)
        self._track_renderer = None
        self.options_panel = None







    def setup(self):
        assert hasattr(self.ui, 'connections')
        
        self.TrackOptionsPanelOwningMixin_on_setup()
        


    def _buildGraphics(self):
        """ called by self.buildUI() which usually is not overriden. """
        

        ## More Involved Mode:
        # self.ui.root_graphics_layout_widget = pg.GraphicsLayoutWidget()
        self.ui.root_graphics_layout_widget = CustomGraphicsLayoutWidget()

        # self.ui.root_view = self.ui.root_graphics_layout_widget.addViewBox()
        ## lock the aspect ratio so pixels are always square
        # self.ui.root_view.setAspectLocked(True)

        ## Create image item
        
        # self.ui.imv = pg.ImageItem(border='w')
        # self.ui.root_view.addItem(self.ui.imv)
        # self.ui.root_view.setRange(QtCore.QRectF(*self.params.image_bounds_extent))

        self.ui.root_plot_viewBox = None
        self.ui.root_plot_viewBox = CustomViewBox()
        self.ui.root_plot_viewBox.setObjectName('RootPlotCustomViewBox')
        
        # Configure datetime axis if reference_datetime is available
        axis_items = {}
        if self.reference_datetime is not None:
            # Create custom DateAxisItem with 12-hour AM/PM format
            date_axis = create_am_pm_date_axis(orientation='bottom')
            if date_axis is not None:
                axis_items['bottom'] = date_axis
        
        # self.ui.root_plot = self.ui.root_graphics_layout_widget.addPlot(row=0, col=0, title=None) # , name=f'PositionDecoder'
        self.ui.root_plot = self.ui.root_graphics_layout_widget.addPlot(row=0, col=0, title=None, viewBox=self.ui.root_plot_viewBox, axisItems=axis_items if axis_items else None)
        self.ui.root_plot.setObjectName('RootPlot')
        # self.ui.root_plot.addItem(self.ui.imv, defaultPadding=0.0)  # add ImageItem to PlotItem
        ## TODO: add item here
        # self.ui.root_plot.showAxes(True)
        self.ui.root_plot.hideButtons() # Hides the auto-scale button
        
        self.ui.root_plot.showAxes(False)     
        # self.ui.root_plot.setRange(xRange=self.params.x_range, yRange=self.params.y_range, padding=0.0)
        # Sets only the panning limits:
        # self.ui.root_plot.setLimits(xMin=self.params.x_range[0], xMax=self.params.x_range[-1], yMin=self.params.y_range[0], yMax=self.params.y_range[-1])

        ## Sets all limits:
        # _x, _y, _width, _height = self.params.image_bounds_extent # [23.923329354140844, 123.85967782096927, 241.7178791533281, 30.256480996256016]
        # self.ui.root_plot.setLimits(minXRange=_width, maxXRange=_width, minYRange=_height, maxYRange=_height)
        # self.ui.root_plot.setLimits(xMin=self.params.x_range[0], xMax=self.params.x_range[-1], yMin=self.params.y_range[0], yMax=self.params.y_range[-1],
        #                             minXRange=_width, maxXRange=_width, minYRange=_height, maxYRange=_height)
        
        self.ui.root_plot.setMouseEnabled(x=True, y=False)
        self.ui.root_plot.setMenuEnabled(enableMenu=False)


        # _conn = vb.sigLeftDrag.connect(on_window_update)


        
        # ## Optional Interactive Color Bar:
        # bar = pg.ColorBarItem(values= (0, 1), colorMap=self.params.cmap, width=5, interactive=False) # prepare interactive color bar
        # # Have ColorBarItem control colors of img and appear in 'plot':
        # bar.setImageItem(self.ui.imv, insert_in=self.ui.root_plot)
        
        self.ui.layout.addWidget(self.ui.root_graphics_layout_widget, 0, 0) # add the GLViewWidget to the layout at 0, 0
        
        # Set the color map:
        # self.ui.imv.setColorMap(self.params.cmap)
        ## Set initial view bounds
        # self.ui.root_view.setRange(QtCore.QRectF(0, 0, 600, 600))
        


    
    def update(self, t, defer_render=False):
        if self.enable_debug_print:
            print(f'PyqtgraphTimeSynchronizedWidget.update(t: {t})')
    
        # # Finds the nearest previous decoded position for the time t:
        # self.last_window_index = np.searchsorted(self.time_window_centers, t, side='left') # side='left' ensures that no future values (later than 't') are ever returned
        # self.last_window_time = self.time_window_centers[self.last_window_index] # If there is no suitable index, return either 0 or N (where N is the length of `a`).
        # Update the plots:
        if not defer_render:
            self._update_plots()


    def _update_plots(self):
        if self.enable_debug_print:
            print(f'PyqtgraphTimeSynchronizedWidget._update_plots()')

        # Update the existing one:
        # self.ui.root_plot.setRange(xRange=self.params.x_range, yRange=self.params.y_range, padding=0.0)
        # Sets only the panning limits:
        # self.ui.root_plot.setLimits(xMin=self.params.x_range[0], xMax=self.params.x_range[-1], yMin=self.params.y_range[0], yMax=self.params.y_range[-1])

        ## Sets all limits:
        # _x, _y, _width, _height = self.params.image_bounds_extent # [23.923329354140844, 123.85967782096927, 241.7178791533281, 30.256480996256016]
        # self.ui.root_plot.setLimits(minXRange=_width, maxXRange=_width, minYRange=_height, maxYRange=_height)
        # self.ui.root_plot.setLimits(xMin=self.params.x_range[0], xMax=self.params.x_range[-1], yMin=self.params.y_range[0], yMax=self.params.y_range[-1],
        #                             minXRange=_width, maxXRange=_width, minYRange=_height, maxYRange=_height)
        
        # Update the plots:
        # curr_time_window_index = self.last_window_index
        # curr_t = self.last_window_time

        # if curr_time_window_index is None or curr_t is None:
        #     return # return without updating

        # self.setWindowTitle(f'{self.windowName} - {image_title} t = {curr_t}')
        # self.setWindowTitle(f'PyqtgraphTimeSynchronizedWidget - {image_title} t = {curr_t}')
        pass

    # ==================================================================================================================== #
    # QT Slots                                                                                                             #
    # ==================================================================================================================== #
    
    @pyqtExceptionPrintingSlot(float, float)
    def on_window_changed(self, start_t, end_t):
        # called when the window is updated
        if self.enable_debug_print:
            print(f'PyqtgraphTimeSynchronizedWidget.on_window_changed(start_t: {start_t}, end_t: {end_t})')
        # if self.enable_debug_print:
        #     profiler = pg.debug.Profiler(disabled=True, delayed=True)

        if (start_t is not None) and (end_t is not None):
            # Convert to datetime then to Unix timestamp if reference_datetime is available.
            # PyQtGraph's DateAxisItem expects Unix timestamps (float) but displays them as dates.
            if self.reference_datetime is not None:
                # If already datetime-like, use directly.
                if isinstance(start_t, (datetime, pd.Timestamp)) and isinstance(end_t, (datetime, pd.Timestamp)):
                    dt_start = pd.Timestamp(start_t)
                    dt_end = pd.Timestamp(end_t)
                elif isinstance(start_t, (int, float)) and isinstance(end_t, (int, float)) and float(start_t) > 1e9 and float(end_t) > 1e9:
                    dt_start = pd.Timestamp(unix_timestamp_to_datetime(float(start_t)))
                    dt_end = pd.Timestamp(unix_timestamp_to_datetime(float(end_t)))
                else:
                    dt_start = float_to_datetime(start_t, self.reference_datetime)
                    dt_end = float_to_datetime(end_t, self.reference_datetime)
                # Convert datetime to Unix timestamp for PyQtGraph (safely handles timezone)
                unix_start = datetime_to_unix_timestamp(dt_start)
                unix_end = datetime_to_unix_timestamp(dt_end)
                self.getRootPlotItem().setXRange(unix_start, unix_end, padding=0)
            else:
                # No reference datetime. If datetime-like, convert to unix timestamps.
                if isinstance(start_t, (datetime, pd.Timestamp)) and isinstance(end_t, (datetime, pd.Timestamp)):
                    unix_start = datetime_to_unix_timestamp(start_t)
                    unix_end = datetime_to_unix_timestamp(end_t)
                    self.getRootPlotItem().setXRange(unix_start, unix_end, padding=0)
                else:
                    self.getRootPlotItem().setXRange(start_t, end_t, padding=0) ## global frame

        self.update(end_t, defer_render=False)
        # if self.enable_debug_print:
        #     profiler('Finished calling _update_plots()')
            


    # def mouse_clicked(self, event):
    #     # Only handle middle mouse button
    #     if event.button() == 2:  # Middle mouse button
    #         pos = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
    #         self.start_pos = pos.x()
    #         self.dragging = True
    #         self.trace_region.hide()  # Reset trace region visibility
    #         event.accept()

    # def mouse_moved(self, event):
    #     if self.dragging and self.start_pos is not None:
    #         # Update the trace region during dragging
    #         current_pos = self.plot_widget.plotItem.vb.mapSceneToView(event)
    #         x_end = current_pos.x()
    #         self.trace_region.setRegion([min(self.start_pos, x_end), max(self.start_pos, x_end)])
    #         self.trace_region.show()  # Show the trace region as it's being defined

    # def mouse_released(self, event):
    #     # Finalize the trace region definition
    #     if event.button() == 2 and self.dragging:
    #         self.dragging = False
    #         self.start_pos = None
    #         print(f"Trace region set to: {self.trace_region.getRegion()}")
            


    def getRootLayout(self) -> QtWidgets.QGridLayout:
        return self.ui.layout
    
    def getRootGraphicsLayoutWidget(self) -> pg.GraphicsLayoutWidget:
        return self.ui.root_graphics_layout_widget
    
    def getRootPlotItem(self) -> pg.PlotItem:
        return self.ui.root_plot
    
    def getRootViewBox(self) -> CustomViewBox:
        return self.ui.root_plot_viewBox
    
    # ==================================================================================================================== #
    # Misc Functionality                                                                                                   #
    # ==================================================================================================================== #
    

    # ==================================================================================================================== #
    # CrosshairsTracingMixin Conformances                                                                                  #
    # ==================================================================================================================== #
    def on_crosshair_mouse_moved(self, pos, plot_item, vb, vLine, name, matrix=None, xbins=None, ybins=None):
        """Handles crosshair updates when mouse moves
        
        Args:
            pos: Mouse position in scene coordinates
            plot_item: The plot item containing the crosshair
            vb: ViewBox reference
            vLine: The vertical line object
            name: Identifier for this crosshair
            matrix: Optional data matrix
            xbins: Optional x bin edges
            ybins: Optional y bin edges
        """
        # Check if mouse is within the plot area
        if not plot_item.sceneBoundingRect().contains(pos):
            # Hide crosshairs when outside plot
            vLine.setVisible(False)
            if self.params.crosshairs_enable_y_trace and 'crosshairs_hLine' in self.plots[name]:
                self.plots[name]['crosshairs_hLine'].setVisible(False)
            return
            
        # Map scene coordinates to data coordinates
        mousePoint = vb.mapSceneToView(pos)
        x_point = mousePoint.x()
        y_point = mousePoint.y() if self.params.crosshairs_enable_y_trace else 0
        
        # Handle discrete vs continuous formatting
        if self.params.should_force_discrete_to_bins:
            x_point_discrete = float(int(round(x_point)))
            y_point_discrete = float(int(round(y_point))) if self.params.crosshairs_enable_y_trace else 0
            
            # Snap to center of bin for display
            x_point = x_point_discrete + 0.5
            y_point = y_point_discrete + 0.5 if self.params.crosshairs_enable_y_trace else 0
            
            index_x = int(x_point_discrete)
            index_y = int(y_point_discrete) if self.params.crosshairs_enable_y_trace else 0
        else:
            index_x = int(x_point)
            index_y = int(y_point) if self.params.crosshairs_enable_y_trace else 0
        
        # Format value string
        value_str = ""
        if matrix is not None:
            shape = np.shape(matrix)
            valid_x = (index_x >= 0 and index_x < shape[0])
            valid_y = (index_y >= 0 and index_y < shape[1]) if self.params.crosshairs_enable_y_trace else True
            
            if valid_x and valid_y:
                # Position component
                position_str = ""
                if self.params.should_force_discrete_to_bins:
                    if (xbins is not None) and (ybins is not None) and self.params.crosshairs_enable_y_trace:
                        position_str = f"(x[{index_x}]={xbins[index_x]:.3f}, y[{index_y}]={ybins[index_y]:.3f})"
                    else:
                        position_str = f"(x={index_x}, y={index_y if self.params.crosshairs_enable_y_trace else index_x})"
                else:
                    position_str = f"(x={x_point:.1f}, y={y_point:.1f})" if self.params.crosshairs_enable_y_trace else f"(x={x_point:.1f})"
                
                # Value component
                value_component = ""
                if valid_x and valid_y:
                    value_component = f"value={matrix[index_x][index_y if self.params.crosshairs_enable_y_trace else 0]:.3f}"
                
                # Final formatted string for PyQtGraph (can use HTML)
                value_str = f"<span style='font-size: 12pt'>{position_str}, <span style='color: green'>{value_component}</span></span>"
        else:
            # No matrix, just show coordinates
            if self.params.should_force_discrete_to_bins:
                if (xbins is not None) and (ybins is not None) and self.params.crosshairs_enable_y_trace:
                    value_str = f"<span style='font-size: 12pt'>(x[{index_x}]={xbins[index_x]:.3f}, y[{index_y}]={ybins[index_y]:.3f})</span>"
                else:
                    value_str = f"<span style='font-size: 12pt'>(x={index_x}, y={index_y if self.params.crosshairs_enable_y_trace else index_x})</span>"
            else:
                value_str = f"<span style='font-size: 12pt'>(x={x_point:.1f}, y={y_point:.1f})</span>" if self.params.crosshairs_enable_y_trace else f"<span style='font-size: 12pt'>(x={x_point:.1f})</span>"
        
        # Update crosshair positions
        vLine.setPos(x_point)
        vLine.setVisible(True)
        
        if self.params.crosshairs_enable_y_trace and 'crosshairs_hLine' in self.plots[name]:
            self.plots[name]['crosshairs_hLine'].setPos(y_point)
            self.plots[name]['crosshairs_hLine'].setVisible(True)
        
        # Emit signal with formatted value
        self.sigCrosshairsUpdated.emit(self, name, value_str)


    def on_crosshair_enter_view(self, plot_item, name):
        """Called when mouse enters the view"""
        if name in self.plots and 'crosshairs_vLine' in self.plots[name]:
            self.plots[name]['crosshairs_vLine'].setVisible(True)
            if 'crosshairs_hLine' in self.plots[name]:
                self.plots[name]['crosshairs_hLine'].setVisible(True)

    def on_crosshair_leave_view(self, plot_item, name):
        """Called when mouse leaves the view"""
        if name in self.plots and 'crosshairs_vLine' in self.plots[name]:
            self.plots[name]['crosshairs_vLine'].setVisible(False)
            if 'crosshairs_hLine' in self.plots[name]:
                self.plots[name]['crosshairs_hLine'].setVisible(False)




    def add_crosshairs(self, plot_item, name, matrix=None, xbins=None, ybins=None, enable_y_trace:bool=False, should_force_discrete_to_bins:Optional[bool]=True, **kwargs):
        """ adds crosshairs that allow the user to hover a bin and have the label dynamically display the bin (x, y) and value.
        
        Uses:
        self.params.should_force_discrete_to_bins
        
        Updates self.plots[name], self.ui.connections[name]
        
        Emits: self.sigCrosshairsUpdated
        
        """
        print(f'PyqtgraphTimeSynchronizedWidget.add_crosshairs(plot_item: {plot_item}, name: "{name}", ...):')
        try:
            # Create ViewBox and crosshair lines
            vb = plot_item.getViewBox()
            
            # Create vertical line for crosshair
            vLine = pg.InfiniteLine(angle=90, movable=False)
            plot_item.addItem(vLine, ignoreBounds=True)
            self.plots[name]['crosshairs_vLine'] = vLine
            vLine.setVisible(False)
            
            # Create horizontal line if y-trace is enabled
            if enable_y_trace:
                hLine = pg.InfiniteLine(angle=0, movable=False)
                plot_item.addItem(hLine, ignoreBounds=True)
                self.plots[name]['crosshairs_hLine'] = hLine
                hLine.setVisible(False)
            
            # Store parameters
            self.params.crosshairs_enable_y_trace = enable_y_trace
            self.params.should_force_discrete_to_bins = should_force_discrete_to_bins
            
            # Connect signals with better error handling
            self.ui.connections[name] = pg.SignalProxy(plot_item.scene().sigMouseMoved, 
                                                    rateLimit=60, 
                                                    slot=lambda evt: self.on_crosshair_mouse_moved(evt[0], vb, vLine, name, matrix, xbins, ybins))
            
            # Connect enter/leave events
            plot_item.getViewBox().setMouseEnabled(x=True, y=False)
            plot_item.scene().sigMouseEntered.connect(lambda: self.on_crosshair_enter_view(plot_item, name))
            plot_item.scene().sigMouseExited.connect(lambda: self.on_crosshair_leave_view(plot_item, name))
            
            # Success message
            print(f"Successfully added crosshairs for {name}")
        except Exception as e:
            print(f"Failed to add crosshair traces for widget: {self}. Error: {str(e)}") # #TODO 2025-07-22 16:40: - [ ] PyqtgraphTimeSynchronizedWidget - Error: 'traceHairs'



    def remove_crosshairs(self, plot_item, name=None):
        print(f'PyqtgraphTimeSynchronizedWidget.remove_crosshairs(plot_item: {plot_item}, name: "{name}"):')
        try:
            # Logic to remove specific or all crosshairs
            if name is None:
                # Remove all crosshairs
                for key in list(self.plots.keys()):
                    if 'crosshairs_vLine' in self.plots[key]:
                        self.plots[key]['crosshairs_vLine'].setParent(None)
                        del self.plots[key]['crosshairs_vLine']
                    if 'crosshairs_hLine' in self.plots[key]:
                        self.plots[key]['crosshairs_hLine'].setParent(None)
                        del self.plots[key]['crosshairs_hLine']
                    # Disconnect signals
                    if key in self.ui.connections:
                        self.ui.connections[key].disconnect()
                        del self.ui.connections[key]
            else:
                # Remove specific crosshair
                if name in self.plots:
                    if 'crosshairs_vLine' in self.plots[name]:
                        self.plots[name]['crosshairs_vLine'].setParent(None)
                        del self.plots[name]['crosshairs_vLine']
                    if 'crosshairs_hLine' in self.plots[name]:
                        self.plots[name]['crosshairs_hLine'].setParent(None)
                        del self.plots[name]['crosshairs_hLine']
                    # Disconnect signal
                    if name in self.ui.connections:
                        self.ui.connections[name].disconnect()
                        del self.ui.connections[name]
            
            # Trigger update
            plot_item.update()
        except Exception as e:
            print(f"Error removing crosshairs: {str(e)}")



    def update_crosshair_trace(self, wants_crosshairs_trace: bool):
        """ updates the crosshair trace peferences
        """
        print(f'PyqtgraphTimeSynchronizedWidget.update_crosshair_trace(wants_crosshairs_trace: {wants_crosshairs_trace}):')
        old_value = deepcopy(self.params.wants_crosshairs)
        did_change: bool = (old_value != wants_crosshairs_trace)
        if did_change:
            self.params.wants_crosshairs = wants_crosshairs_trace
            root_plot_item = self.getRootPlotItem()
            if wants_crosshairs_trace:
                print(f'\tadding crosshairs...')
                self.add_crosshairs(plot_item=root_plot_item, name='root_plot_item', matrix=None, xbins=None, ybins=None, enable_y_trace=False)
                print(f'\tdone.')
            else:
                print(f'\tremoving crosshairs...')
                self.remove_crosshairs(plot_item=root_plot_item, name='root_plot_item')
                print(f'\tdone.')
        else:
            print(f'\tno change!')
    




    # ==================================================================================================================================================================================================================================================================================== #
    # Options Panel Mixin                                                                                                                                                                                                                                                                  #
    # ==================================================================================================================================================================================================================================================================================== #

    def set_track_renderer(self, track_renderer):
        """Set the track renderer reference for this widget.
        
        Args:
            track_renderer: TrackRenderer instance associated with this widget
        """
        self._track_renderer = track_renderer
    
    @property
    def optionsPanel(self):
        """Property to support camelCase naming convention for dock compatibility."""
        return self.options_panel
    
    @optionsPanel.setter
    def optionsPanel(self, value):
        """Property setter to support camelCase naming convention for dock compatibility."""
        self.options_panel = value
    
    ## Overrides `TrackOptionsPanelOwningMixin.getOptionalPanel(...)`
    def getOptionsPanel(self):
        """Get the options panel for this widget.
        
        Returns:
            QWidget with options panel, or None if not applicable
        """
        # Only create options panel if we have a track renderer
        if self._track_renderer is None:
            return None

        # Use consistent connections storage (same as rest of class)
        # Initialize connections if it doesn't exist (handles DynamicParameters properly)
        if isinstance(self.ui, DynamicParameters):
            # Need this workaround because hasattr fails for DynamicParameters/PhoUIContainer right now:
            self.ui.setdefault('connections', ConnectionsContainer())
        else:
            if not hasattr(self.ui, 'connections') or self.ui.connections is None:
                self.ui.connections = ConnectionsContainer()

        # Create options panel if not already created
        if self.options_panel is None:
            # Handle both TrackRenderer and DetailRenderer directly
            # If _track_renderer has a detail_renderer attribute, it's a TrackRenderer
            # Otherwise, it's a DetailRenderer itself
            if hasattr(self._track_renderer, 'detail_renderer'):
                # It's a TrackRenderer
                detail_renderer = self._track_renderer.detail_renderer
                track_renderer = self._track_renderer
            else:
                # It's a DetailRenderer directly
                detail_renderer = self._track_renderer
                track_renderer = None
            
            desired_connections = {}
            is_eeg_spectrogram_panel = False
            is_eeg_fp_gfp_panel = False
            if track_renderer is not None:
                _eeg_spec_ds_type = None
                try:
                    from pypho_timeline.rendering.datasources.specific.eeg import EEGSpectrogramTrackDatasource as _eeg_spec_ds_type
                except ImportError:
                    pass
                if _eeg_spec_ds_type is not None and isinstance(track_renderer.datasource, _eeg_spec_ds_type):
                    from pypho_timeline.widgets.track_options_panels import EEGSpectrogramTrackOptionsPanel
                    self.options_panel = EEGSpectrogramTrackOptionsPanel(track_renderer=track_renderer)
                    desired_connections['options_panel.optionsChanged'] = (self.options_panel.optionsChanged, self.TrackOptionsPanelOwningMixin_optionsChanged)
                    desired_connections['options_panel.onOptionsAccepted'] = (self.options_panel.onOptionsAccepted, self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                    desired_connections['options_panel.onOptionsRejected'] = (self.options_panel.onOptionsRejected, self.TrackOptionsPanelOwningMixin_onOptionsRejected)
                    if hasattr(track_renderer, 'on_options_changed'):
                        desired_connections['on_options_changed'] = (self.optionsChanged, track_renderer.on_options_changed)
                    if hasattr(track_renderer, 'on_options_accepted'):
                        desired_connections['on_options_accepted'] = (self.onOptionsAccepted, track_renderer.on_options_accepted)
                    if hasattr(track_renderer, 'on_options_rejected'):
                        desired_connections['on_options_rejected'] = (self.onOptionsRejected, track_renderer.on_options_rejected)
                    self.ui.connections['spectrogram_options_applied'] = self.options_panel.spectrogramOptionsApplied.connect(track_renderer.apply_eeg_spectrogram_options_from_datasource)
                    if hasattr(track_renderer, 'set_options_panel'):
                        track_renderer.set_options_panel(self.options_panel)
                    is_eeg_spectrogram_panel = True
                if not is_eeg_spectrogram_panel:
                    _eeg_fp_ds_type = None
                    try:
                        from pypho_timeline.rendering.datasources.specific.eeg import EEGFPTrackDatasource as _eeg_fp_ds_type
                    except ImportError:
                        pass
                    if _eeg_fp_ds_type is not None and isinstance(track_renderer.datasource, _eeg_fp_ds_type):
                        from pypho_timeline.widgets.track_options_panels import LinePowerGFPTrackOptionsPanel
                        self.options_panel = LinePowerGFPTrackOptionsPanel(track_renderer=track_renderer)
                        desired_connections['options_panel.optionsChanged'] = (self.options_panel.optionsChanged, self.TrackOptionsPanelOwningMixin_optionsChanged)
                        desired_connections['options_panel.onOptionsAccepted'] = (self.options_panel.onOptionsAccepted, self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                        desired_connections['options_panel.onOptionsRejected'] = (self.options_panel.onOptionsRejected, self.TrackOptionsPanelOwningMixin_onOptionsRejected)
                        if hasattr(track_renderer, 'on_options_changed'):
                            desired_connections['on_options_changed'] = (self.optionsChanged, track_renderer.on_options_changed)
                        if hasattr(track_renderer, 'on_options_accepted'):
                            desired_connections['on_options_accepted'] = (self.onOptionsAccepted, track_renderer.on_options_accepted)
                        if hasattr(track_renderer, 'on_options_rejected'):
                            desired_connections['on_options_rejected'] = (self.onOptionsRejected, track_renderer.on_options_rejected)
                        self.ui.connections['gfp_options_applied'] = self.options_panel.gfpOptionsApplied.connect(track_renderer.apply_line_power_gfp_options_from_datasource)
                        if hasattr(track_renderer, 'set_options_panel'):
                            track_renderer.set_options_panel(self.options_panel)
                        is_eeg_fp_gfp_panel = True

            # Check if detail renderer has channel_names (channel-based renderer)
            if not is_eeg_spectrogram_panel and not is_eeg_fp_gfp_panel and hasattr(detail_renderer, 'channel_names') and detail_renderer.channel_names is not None:
                # Create channel visibility panel for tracks with channels
                from pypho_timeline.widgets.track_options_panels import TrackChannelVisibilityOptionsPanel
                
                channel_names = detail_renderer.channel_names
                # Get initial visibility from track_renderer if available, otherwise from detail_renderer, or create default
                if track_renderer is not None and hasattr(track_renderer, 'channel_visibility'):
                    initial_visibility = track_renderer.channel_visibility.copy()
                elif hasattr(detail_renderer, 'channel_visibility') and detail_renderer.channel_visibility:
                    initial_visibility = detail_renderer.channel_visibility.copy()
                else:
                    # Create default visibility (all channels visible)
                    initial_visibility = {channel: True for channel in channel_names}
                
                self.options_panel = TrackChannelVisibilityOptionsPanel(channel_names=channel_names, initial_visibility=initial_visibility)
                
                # # Forward panel signals to widget's mixin signals
                # self.options_panel.optionsChanged.connect(self.TrackOptionsPanelOwningMixin_optionsChanged)
                # self.options_panel.onOptionsAccepted.connect(self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                # self.options_panel.onOptionsRejected.connect(self.TrackOptionsPanelOwningMixin_onOptionsRejected)
                
                # Build desired connections only if track_renderer exists and has the methods
                # Connect mixin signals (which are forwarded from panel) to track_renderer
                desired_connections = {}

                # self.options_panel.optionsChanged.connect(self.TrackOptionsPanelOwningMixin_optionsChanged)
                # self.options_panel.onOptionsAccepted.connect(self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                # self.options_panel.onOptionsRejected.connect(self.TrackOptionsPanelOwningMixin_onOptionsRejected)

                # if hasattr(self, 'on_options_changed'):
                desired_connections['options_panel.optionsChanged'] = (self.options_panel.optionsChanged, self.TrackOptionsPanelOwningMixin_optionsChanged)
                # if hasattr(self, 'on_options_accepted'):
                desired_connections['options_panel.onOptionsAccepted'] = (self.options_panel.onOptionsAccepted, self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                # if hasattr(self, 'on_options_rejected'):
                desired_connections['options_panel.onOptionsRejected'] = (self.options_panel.onOptionsRejected, self.TrackOptionsPanelOwningMixin_onOptionsRejected)

                if track_renderer is not None:
                    if hasattr(track_renderer, 'on_options_changed'):
                        desired_connections['on_options_changed'] = (self.optionsChanged, track_renderer.on_options_changed)
                    if hasattr(track_renderer, 'on_options_accepted'):
                        desired_connections['on_options_accepted'] = (self.onOptionsAccepted, track_renderer.on_options_accepted)
                    if hasattr(track_renderer, 'on_options_rejected'):
                        desired_connections['on_options_rejected'] = (self.onOptionsRejected, track_renderer.on_options_rejected)

                # Connect panel signals to track renderer if available
                if track_renderer is not None and hasattr(track_renderer, 'update_channel_visibility'):
                    # desired_connections['update_channel_visibility'] = (self.options_panel.channelVisibilityChanged, track_renderer.update_channel_visibility)
                    self.ui.connections['update_channel_visibility'] = self.options_panel.channelVisibilityChanged.connect(track_renderer.update_channel_visibility)
                    # Store reference in track renderer for bidirectional updates
                    if hasattr(track_renderer, 'set_options_panel'):
                        track_renderer.set_options_panel(self.options_panel)

            elif not is_eeg_spectrogram_panel and not is_eeg_fp_gfp_panel:
                # Create basic options panel for tracks without channels
                from pypho_timeline.widgets.track_options_panels import OptionsPanel
                self.options_panel = OptionsPanel()

                # Build desired connections: panel → mixin, then mixin → track_renderer when present
                desired_connections = {}
                # Forward panel signals to widget's mixin signals
                desired_connections['options_panel.optionsChanged'] = (self.options_panel.optionsChanged, self.TrackOptionsPanelOwningMixin_optionsChanged)
                desired_connections['options_panel.onOptionsAccepted'] = (self.options_panel.onOptionsAccepted, self.TrackOptionsPanelOwningMixin_onOptionsAccepted)
                desired_connections['options_panel.onOptionsRejected'] = (self.options_panel.onOptionsRejected, self.TrackOptionsPanelOwningMixin_onOptionsRejected)

                if track_renderer is not None:
                    if hasattr(track_renderer, 'on_options_changed'):
                        desired_connections['on_options_changed'] = (self.optionsChanged, track_renderer.on_options_changed)
                    if hasattr(track_renderer, 'on_options_accepted'):
                        desired_connections['on_options_accepted'] = (self.onOptionsAccepted, track_renderer.on_options_accepted)
                    if hasattr(track_renderer, 'on_options_rejected'):
                        desired_connections['on_options_rejected'] = (self.onOptionsRejected, track_renderer.on_options_rejected)

            # Connect panel signals to track renderer if available
            if track_renderer is not None:
                for k, (a_sig, a_slot) in desired_connections.items():
                    # Safely disconnect existing connection if present
                    extant_conn = self.ui.connections.pop(k, None)
                    if extant_conn is not None:
                        try:
                            print(f'disconnecting "{k}" signal')
                            a_sig.disconnect(extant_conn)
                        except (TypeError, RuntimeError) as e:
                            # Connection may already be disconnected or invalid
                            print(f'Warning: Could not disconnect "{k}" signal: {e}')

                    # Make new connection if track_renderer has the method
                    if hasattr(track_renderer, k):
                        try:
                            self.ui.connections[k] = a_sig.connect(a_slot)
                            print(f'Connected "{k}" signal from options panel to track_renderer.{k}')
                        except (TypeError, AttributeError) as e:
                            print(f'Warning: Could not connect "{k}" signal: {e}')
                    else:
                        print(f'Warning: track_renderer does not have method "{k}"')

        
        return self.options_panel
            

# included_epochs = None
# computation_config = active_session_computation_configs[0]
# active_time_dependent_placefields2D = PfND_TimeDependent(deepcopy(sess.spikes_df.copy()), deepcopy(sess.position), epochs=included_epochs,
#                                   speed_thresh=computation_config.speed_thresh, frate_thresh=computation_config.frate_thresh,
#                                   grid_bin=computation_config.grid_bin, smooth=computation_config.smooth)
# curr_occupancy_plotter = PyqtgraphTimeSynchronizedWidget(active_time_dependent_placefields2D)
# curr_occupancy_plotter.show()


    # ==================================================================================================================================================================================================================================================================================== #
    # PlotImageExportableMixin Conformances                                                                                                                                                                                                                                                #
    # ==================================================================================================================================================================================================================================================================================== #

    def export_as_img_arr(self, start=None, end=None, dpi=150,
                          info=None,
                        #    y_offset = 0, y_min = 0.0,
                        **kwargs,
        ) -> NDArray:
        """ 
        
        """
        from pyqtgraph.exporters import ImageExporter
        from PyQt5.QtGui import QImage

        debug_print = kwargs.pop('debug_print', False)
        
        # pyqtgraph-backed tracks
        
        # # ## Data units version: for 3 tracks, we get [[-4.4, 0.4], [-4.0, 45.5], [0, 1]]
        # # y_min, y_max = t.getViewBox().viewRange()[1]
        # # h = y_max - y_min
        # # extent = [x_min, x_max, y_offset, y_offset+h]

        # ## Figure units version:
        # #t.get_extent() is like [-2.84147705365001e-15, 1458.5500000000002, 0.0, 287.7697841726619] and in data units
        # y_min = 0.0
        # y_max = track_heights[track_IDX] ## these are in data units, like [0.0, 287.7697841726619] and so the same for many tracks
        # h = y_max - y_min ## in data units
        # extent = [x_min, x_max, y_offset, (y_offset+h)]

        # t = self.active_plot_target
        # info = dict(kind="pg", subkind="PlotItem", obj=t, extent=extent, y_height=h)
        
        # ## have info obj:
        # pi = info['obj']
        # vb = pi.getViewBox()
        # orig_x, orig_y = vb.viewRange()
        
        # # Temporarily break X-link if present (e.g., for new_curves_separate_plot)
        # # This prevents the linked plot from overriding the X range change during export
        # orig_x_link = vb.linkedView(pg.ViewBox.XAxis)  # Get current X-axis link
        # if orig_x_link is not None:
        #     pi.setXLink(None)  # Temporarily unlink
        
        # pi.setXRange(start, end, padding=0) ## set to this chunk
        # pi.setYRange(*orig_y, padding=0)


        exporter = ImageExporter(self.active_plot_target)
        if (start is not None) or (end is not None):
            # exporter.parameters()['width'] = int(figsize[0]*dpi)
            # exporter.parameters()['height'] = int(((figsize[1]/len(page_chunks))*dpi)/len(tracks))
            exporter.parameters()['width'] = int((end - start) * dpi) # AI suggests I should be using `figsize[0] * dpi` - I don't think this is right.
        if (info is not None):
            exporter.parameters()['height'] = int((info['extent'][3] - info['extent'][2]) * dpi)
            

        if debug_print:
            print(f"\texporter.parameters(): w: {exporter.parameters()['width']}, h: {exporter.parameters()['height']}")
        # exporter.parameters()['width'] = int(figsize[0]*dpi)
        # exporter.parameters()['height'] = int((figsize[1]/len(page_chunks))*dpi/len(tracks))
        img = exporter.export(toBytes=True)
        if isinstance(img, QImage):
            w, h = img.width(), img.height()
            ptr = img.bits(); ptr.setsize(img.byteCount())
            # QImage from pyqtgraph is typically in BGRA byte order.
            raw = np.array(ptr).reshape(h, w, 4).astype(np.float32) / 255.0
            b = raw[:, :, 0]
            g = raw[:, :, 1]
            r = raw[:, :, 2]
            a = raw[:, :, 3]
            rgb = np.stack([r, g, b], axis=-1)
            # Composite over white background so grid and image blend as on-screen
            bg = np.ones_like(rgb)
            comp = rgb * a[..., None] + bg * (1.0 - a[..., None])
            arr = (comp * 255).astype(np.uint8)
        else:
            arr = np.array(img)

        return arr


