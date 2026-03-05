"""Performant DataFrame table widget for pyPhoTimeline.

This module provides a widget for displaying pandas DataFrames in a table view,
with support for synchronized scrolling based on time.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Union, List

from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from pypho_timeline.core.time_synchronized_plotter_base import TimeSynchronizedPlotterBase
from pypho_timeline.utils.logging_util import get_rendering_logger
from pypho_timeline.utils.datetime_helpers import datetime_to_float, float_to_datetime, UNIX_EPOCH_UTC

logger = get_rendering_logger(__name__)

class DataFrameTableModel(QtCore.QAbstractTableModel):
    """A performant table model for pandas DataFrames."""
    
    def __init__(self, df: pd.DataFrame = pd.DataFrame(), parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            value = self._df.iloc[row, col]
            # Format based on type
            if isinstance(value, (float, np.float64)):
                return f"{value:.4f}"
            if isinstance(value, (datetime, pd.Timestamp)):
                return value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            return str(value)
        
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            # Right-align numbers, left-align others
            value = self._df.iloc[row, col]
            if isinstance(value, (int, float, np.number)):
                return QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
            return QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            if orientation == QtCore.Qt.Orientation.Vertical:
                # return str(self._df.index[section])
                return section + 1 # Row numbers starting from 1
        return None

    def update_data(self, df: pd.DataFrame):
        """Update the model with a new DataFrame."""
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def get_dataframe(self) -> pd.DataFrame:
        return self._df


class DataFrameTableWidget(TimeSynchronizedPlotterBase):
    """Widget for displaying a pandas DataFrame in a performant table.
    
    Can be synchronized to a time-based viewport.
    """
    
    def __init__(self, df: pd.DataFrame = pd.DataFrame(), time_column: Optional[str] = None, 
                 name: str = 'DataFrameTableWidget', application_name=None, window_name=None, 
                 reference_datetime: Optional[datetime] = None, parent=None, **kwargs):
        """Initialize the DataFrame table widget.
        
        Args:
            df: The pandas DataFrame to display
            time_column: The name of the column containing timestamps for synchronization.
                         If None, it tries to find 'timestamp', 'time', or 't'.
            name: Widget name
            reference_datetime: Reference datetime for synchronization
            parent: Parent widget
        """
        # TimeSynchronizedPlotterBase.__init__ calls setup() and buildUI()
        super().__init__(application_name=application_name, window_name=(window_name or name), parent=parent)
        
        self.setObjectName(name)
        self.df = df
        self._is_synchronized = True
        self.time_column = time_column
        self.reference_datetime = reference_datetime or UNIX_EPOCH_UTC
        
        # If time_column is not specified, try to guess it
        if self.time_column is None and not self.df.empty:
            possible_cols = ['timestamp', 'time', 't', 't_start', 'DateTime']
            for col in possible_cols:
                if col in self.df.columns:
                    self.time_column = col
                    break
        
        # Build UI
        self.buildUI()
        
        # Set initial data
        if not self.df.empty:
            self.set_dataframe(self.df)

    def setup(self):
        """Perform particular setup (called by TimeSynchronizedPlotterBase.__init__)"""
        # self.params = VisualizationParameters(self.applicationName)
        # We don't need a lot of setup here as we don't have many custom params yet
        pass

    def buildUI(self):
        """Build the UI components (called by TimeSynchronizedPlotterBase.__init__)"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Control panel
        control_layout = QtWidgets.QHBoxLayout()
        
        # Sync toggle
        self.sync_button = QtWidgets.QPushButton("Sync")
        self.sync_button.setCheckable(True)
        self.sync_button.setChecked(self._is_synchronized)
        self.sync_button.toggled.connect(self._on_sync_toggled)
        self.sync_button.setToolTip("Toggle synchronization with timeline")
        
        # Search/Filter
        search_label = QtWidgets.QLabel("Filter:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Filter rows...")
        self.search_input.textChanged.connect(self._on_search_changed)
        
        control_layout.addWidget(self.sync_button)
        control_layout.addWidget(search_label)
        control_layout.addWidget(self.search_input)
        
        layout.addLayout(control_layout)
        
        # Table view
        self.table_view = QtWidgets.QTableView()
        self.model = DataFrameTableModel()
        self.table_view.setModel(self.model)
        
        # Performance optimizations for QTableView
        self.table_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setDefaultSectionSize(20) # Compact rows
        self.table_view.horizontalHeader().setStretchLastSection(True)
        
        # Use monospace font for table
        font = QtGui.QFont("Consolas", 8)
        if not font.exactMatch():
            font = QtGui.QFont("Courier", 8)
        self.table_view.setFont(font)
        
        layout.addWidget(self.table_view)
        
        self.setLayout(layout)

    def set_dataframe(self, df: pd.DataFrame):
        """Update the displayed DataFrame."""
        self.df = df
        self.model.update_data(df)
        
        # If we have a time column, ensure it's sorted for performance
        if self.time_column in self.df.columns:
            # We don't necessarily want to sort the user's data if they didn't,
            # but searchsorted requires it. Maybe we just check if it's sorted.
            self._is_time_sorted = self.df[self.time_column].is_monotonic_increasing
        else:
            self._is_time_sorted = False

    def _on_sync_toggled(self, checked: bool):
        self._is_synchronized = checked
        if checked:
            self.sync_button.setText("Sync ON")
            self.sync_button.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.sync_button.setText("Sync OFF")
            self.sync_button.setStyleSheet("")

    def _on_search_changed(self, text: str):
        """Simple filter implementation."""
        if not text:
            self.model.update_data(self.df)
            return
            
        # Basic case-insensitive search across all columns
        mask = np.column_stack([self.df[col].astype(str).str.contains(text, case=False, na=False) for col in self.df.columns]).any(axis=1)
        filtered_df = self.df[mask]
        self.model.update_data(filtered_df)

    def on_window_changed(self, start_t: float, end_t: float):
        """Handle time window change from timeline.
        
        Args:
            start_t: Start time of viewport (Unix timestamp)
            end_t: End time of viewport (Unix timestamp)
        """
        if not self._is_synchronized or self.df.empty or self.time_column not in self.df.columns:
            return
            
        # Find the index of the first row >= start_t
        try:
            time_values = self.df[self.time_column]
            first_val = time_values.iloc[0]
            
            # Handle datetime vs float
            if isinstance(first_val, (datetime, pd.Timestamp)):
                start_dt = float_to_datetime(start_t, self.reference_datetime)
                # Convert to pd.Timestamp for better compatibility with pandas series
                start_dt = pd.Timestamp(start_dt)
                
                # Ensure same awareness
                if first_val.tzinfo is None and start_dt.tzinfo is not None:
                    start_dt = start_dt.tz_localize(None)
                elif first_val.tzinfo is not None and start_dt.tzinfo is None:
                    # Try to match timezone
                    start_dt = start_dt.tz_localize(first_val.tzinfo)
            else:
                start_dt = start_t
            
            if self._is_time_sorted:
                # Use pandas Series.searchsorted which handles datetime64 vs Timestamp correctly
                idx = time_values.searchsorted(start_dt)
            else:
                # Fallback for unsorted data (less performant)
                mask = time_values >= start_dt
                if mask.any():
                    # Find first index where mask is True
                    idx_val = time_values[mask].index[0]
                    # Convert index value to integer row position
                    idx = self.df.index.get_loc(idx_val)
                else:
                    idx = len(self.df)
            
            if idx < len(self.df):
                # Scroll to row
                index = self.model.index(idx, 0)
                self.table_view.scrollTo(index, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop)
                # Optionally select the row
                self.table_view.selectRow(idx)
                
        except Exception as e:
            logger.error(f"Error in DataFrameTableWidget.on_window_changed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @property
    def active_plot_target(self):
        """Implement TimeSynchronizedPlotterBase requirement."""
        return self.table_view

    def update(self, t, defer_render=False):
        """Implement TimeSynchronizedPlotterBase requirement."""
        # This is called by on_window_changed in the base class, 
        # but we override on_window_changed directly.
        pass

__all__ = ['DataFrameTableModel', 'DataFrameTableWidget']
