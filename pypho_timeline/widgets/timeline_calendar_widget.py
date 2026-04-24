"""
Timeline Calendar Widget for pyPhoTimeline library.

This widget provides a highly-performant and responsive scrolling timeline calendar.
It draws fixed regions to represent the days, with subticks for hours.
It includes a LinearRegionItem that represents the current viewport width and allows
clicking/dragging to pan the timeline.
"""

from typing import Tuple, List, Dict, Optional, Union
from datetime import datetime, timedelta, timezone
from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import pandas as pd
import pyqtgraph as pg

# Use specific path if possible, but fallback to standard pg
try:
    from pypho_timeline.EXTERNAL.pyqtgraph.graphicsItems.LinearRegionItem import LinearRegionItem
except ImportError:
    from pyqtgraph.graphicsItems.LinearRegionItem import LinearRegionItem

from pypho_timeline.utils.datetime_helpers import (
    datetime_to_unix_timestamp,
    unix_timestamp_to_datetime,
    float_to_datetime,
    datetime_to_float,
    create_am_pm_date_axis,
    to_display_timezone
)

class ClickableLinearRegionItem(LinearRegionItem):
    """Subclass of LinearRegionItem that handles jump-to-click if requested."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setZValue(100) # Ensure it's on top


class TimelineCalendarWidget(pg.PlotWidget):
    """A scrolling timeline calendar widget using pyqtgraph.
    
    This widget shows a broad view of the timeline, with days and hours marked.
    It provides a LinearRegionItem to show and control the current viewport of the main timeline.
    
    Example:
        calendar = TimelineCalendarWidget()
        calendar.set_total_range(start_dt, end_dt)
        calendar.set_active_window(window_start_dt, window_end_dt)
        calendar.sigWindowChanged.connect(on_window_changed)
    """
    
    sigWindowChanged = QtCore.Signal(float, float) # (start, end) timestamps in seconds (Unix)
    
    def __init__(self, parent=None, **kwargs):
        # Use DateAxisItem for the x-axis
        axis_item = create_am_pm_date_axis(orientation='bottom')
        if axis_item is None:
            axis_item = pg.DateAxisItem(orientation='bottom')
        super().__init__(parent=parent, axisItems={'bottom': axis_item}, **kwargs)
        
        # Configure look and feel
        self.setBackground('w') 
        self.showAxis('left', False) # No y-axis needed
        self.setYRange(0, 1, padding=0)
        self.getViewBox().setMouseEnabled(x=True, y=False) # Only x panning/zooming
        self.getViewBox().setLimits(yMin=0, yMax=1)
        self.getPlotItem().setMenuEnabled(False) # Disable right-click menu
        self.getPlotItem().hideButtons() # Hide auto-scale buttons
        
        # Initialize properties
        self._total_start = None
        self._total_end = None
        self._active_start = None
        self._active_end = None
        
        # Create day/hour graphics storage
        self._day_regions = []
        self._hour_lines = []
        self._day_labels = []
        
        # Create the active window region
        self.region = ClickableLinearRegionItem([0, 1], orientation='vertical', 
                                              brush=QtGui.QColor(100, 150, 255, 100),
                                              hoverBrush=QtGui.QColor(100, 150, 255, 150),
                                              pen=pg.mkPen(color=(50, 100, 200), width=1.5))
        self.addItem(self.region)
        
        # Connect region signals
        self.region.sigRegionChanged.connect(self._on_region_changed)
        
        # Set a fixed height for the calendar
        self.setFixedHeight(80)
        
    def set_total_range(self, start: Union[float, datetime, pd.Timestamp], 
                       end: Union[float, datetime, pd.Timestamp]):
        """Set the total range shown by the calendar.
        
        Args:
            start: Start of the timeline (Unix timestamp or datetime)
            end: End of the timeline (Unix timestamp or datetime)
        """
        if isinstance(start, (datetime, pd.Timestamp)):
            self._total_start = datetime_to_unix_timestamp(start)
        else:
            self._total_start = float(start)
            
        if isinstance(end, (datetime, pd.Timestamp)):
            self._total_end = datetime_to_unix_timestamp(end)
        else:
            self._total_end = float(end)
            
        # Ensure we have a valid range
        if self._total_end <= self._total_start:
            self._total_end = self._total_start + 1.0
            
        self.setXRange(self._total_start, self._total_end, padding=0.01)
        # Fix the view range so it doesn't wander
        self.getViewBox().setLimits(xMin=self._total_start, xMax=self._total_end)
        
        self._update_background()
        
    def set_active_window(self, start: Union[float, datetime, pd.Timestamp], 
                          end: Union[float, datetime, pd.Timestamp]):
        """Update the LinearRegionItem position without emitting sigWindowChanged.
        
        Args:
            start: Start of the active window (Unix timestamp or datetime)
            end: End of the active window (Unix timestamp or datetime)
        """
        if isinstance(start, (datetime, pd.Timestamp)):
            self._active_start = datetime_to_unix_timestamp(start)
        else:
            self._active_start = float(start)
            
        if isinstance(end, (datetime, pd.Timestamp)):
            self._active_end = datetime_to_unix_timestamp(end)
        else:
            self._active_end = float(end)
            
        # Temporarily block signals to avoid recursion if connected back to main timeline
        self.region.blockSignals(True)
        self.region.setRegion([self._active_start, self._active_end])
        self.region.blockSignals(False)
        
    def _on_region_changed(self):
        """Internal handler for region movements."""
        r_start, r_end = self.region.getRegion()
        # Constrain to total range
        if self._total_start is not None and self._total_end is not None:
            width = r_end - r_start
            if r_start < self._total_start:
                r_start = self._total_start
                r_end = r_start + width
                self.region.blockSignals(True)
                self.region.setRegion([r_start, r_end])
                self.region.blockSignals(False)
            elif r_end > self._total_end:
                r_end = self._total_end
                r_start = r_end - width
                self.region.blockSignals(True)
                self.region.setRegion([r_start, r_end])
                self.region.blockSignals(False)

        self._active_start = r_start
        self._active_end = r_end
        self.sigWindowChanged.emit(r_start, r_end)

    def _update_background(self):
        """Redraw day and hour markers based on total range."""
        # Clear existing markers
        for item in self._day_regions:
            self.removeItem(item)
        for item in self._hour_lines:
            self.removeItem(item)
        if hasattr(self, '_day_labels'):
            for item in self._day_labels:
                self.removeItem(item)
            
        self._day_regions = []
        self._hour_lines = []
        self._day_labels = []
        
        if self._total_start is None or self._total_end is None:
            return
            
        # Convert to display timezone datetime for consistent local day boundaries
        start_dt = unix_timestamp_to_datetime(self._total_start)
        end_dt = unix_timestamp_to_datetime(self._total_end)
        start_dt_local = to_display_timezone(start_dt)
        end_dt_local = to_display_timezone(end_dt)
        
        # Calculate day boundaries
        current_day_start = start_dt_local.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current_day_start < end_dt_local:
            next_day_start = current_day_start + timedelta(days=1)
            
            r_start = datetime_to_unix_timestamp(current_day_start)
            r_end = datetime_to_unix_timestamp(next_day_start)
            
            # Draw Day Label
            label_text = current_day_start.strftime('%a %d') # "Mon 05"
            label = pg.TextItem(text=label_text, color=(100, 100, 100), anchor=(0, 0))
            label.setPos(max(self._total_start, r_start), 1.0) # Position at top
            self.addItem(label)
            self._day_labels.append(label)

            if r_start >= self._total_start:
                # Strong vertical line at day boundary
                line = pg.InfiniteLine(pos=r_start, angle=90, pen=pg.mkPen(color=(100, 100, 100), width=1.5))
                line.setZValue(-4)
                self.addItem(line)
                self._hour_lines.append(line)

            # Background fill
            fill_start = max(self._total_start, r_start)
            fill_end = min(self._total_end, r_end)
            
            if fill_start < fill_end:
                if current_day_start.day % 2 == 0:
                    color = QtGui.QColor(245, 245, 245)
                else:
                    color = QtGui.QColor(220, 220, 220)
                
                day_box = pg.LinearRegionItem([fill_start, fill_end], orientation='vertical', 
                                              brush=color, movable=False)
                day_box.setZValue(-10)
                self.addItem(day_box)
                self._day_regions.append(day_box)

            # 2. Draw 6-hour subticks within the day
            for h in [6, 12, 18]:
                sub_hour = current_day_start + timedelta(hours=h)
                h_ts = datetime_to_unix_timestamp(sub_hour)
                if self._total_start < h_ts < self._total_end:
                    # Fainter vertical line for 6-hour divisions
                    line = pg.InfiniteLine(pos=h_ts, angle=90, pen=pg.mkPen(color=(180, 180, 180), width=0.8, style=QtCore.Qt.PenStyle.DashLine))
                    line.setZValue(-5)
                    self.addItem(line)
                    self._hour_lines.append(line)
                
            current_day_start = next_day_start
            
        range_duration = end_dt_local - start_dt_local
        if range_duration < timedelta(days=2):
            current_hour = start_dt_local.replace(minute=0, second=0, microsecond=0)
            while current_hour < end_dt_local:
                h_ts = datetime_to_unix_timestamp(current_hour)
                # Skip if already drawn as day boundary or 6-hour tick
                if h_ts > self._total_start and current_hour.hour % 6 != 0:
                    line = pg.InfiniteLine(pos=h_ts, angle=90, pen=pg.mkPen(color=(210, 210, 210), width=0.5))
                    line.setZValue(-6)
                    self.addItem(line)
                    self._hour_lines.append(line)
                current_hour += timedelta(hours=1)

    def mousePressEvent(self, ev):
        """Override to move region on click if outside the current region."""
        if ev.button() == QtCore.Qt.LeftButton:
            # Map click position to timestamp
            pos = ev.pos()
            timestamp = self.getPlotItem().vb.mapSceneToView(pos).x()
            
            r_start, r_end = self.region.getRegion()
            width = r_end - r_start
            
            # If click is outside the region, move the region to center on click
            # (Standard LinearRegionItem handles clicks ON it for dragging)
            if timestamp < r_start or timestamp > r_end:
                new_start = timestamp - width/2
                new_end = timestamp + width/2
                
                # Constrain to total range
                if self._total_start is not None and self._total_end is not None:
                    if new_start < self._total_start:
                        new_start = self._total_start
                        new_end = new_start + width
                    if new_end > self._total_end:
                        new_end = self._total_end
                        new_start = new_end - width
                
                self.region.setRegion([new_start, new_end])
                # Note: sigRegionChanged will be emitted by setRegion, 
                # which we've connected to self._on_region_changed
                
                # We also want to initiate dragging immediately if the user holds and moves
                # We can do this by forwarding the event to the region if we want,
                # but standard pyqtgraph might already handle it if we positioned it under the mouse.
                
        super().mousePressEvent(ev)

    def sizeHint(self):
        return QtCore.QSize(600, 80)
