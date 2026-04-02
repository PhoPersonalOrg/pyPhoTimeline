from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd
from qtpy import QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any, Sequence, Mapping, TYPE_CHECKING
from datetime import datetime
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
# import pyqtgraph as pg
# from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
# from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
# from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
# from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
# from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
# from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
import pyqtgraph as pg
from phopymnehelper.helpers.dataframe_accessor_helpers import CommonDataFrameAccessorMixin
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, RawProvidingTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode, ChannelNormalizationModeNormalizingMixin
from phopymnehelper.motion_data import BadMotionDataFrame
from phopymnehelper.SavedSessionsProcessor import DataModalityType

from pypho_timeline.utils.logging_util import get_rendering_logger
logger = get_rendering_logger(__name__)

if TYPE_CHECKING:
    import mne
    from phopymnehelper.xdf_files import LabRecorderXDF

try:
    from pyqtgraph.graphicsItems.LinearRegionItem import LinearRegionItem
except ImportError:
    LinearRegionItem = pg.LinearRegionItem




# ==================================================================================================================================================================================================================================================================================== #
# MotionPlotDetailRenderer - Renders motion data as line plots.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #

## TODO: should inherit from `GenericPlotDetailRenderer`
class MotionPlotDetailRenderer(ChannelNormalizationModeNormalizingMixin, DetailRenderer):
    """Detail renderer for motion tracks that displays motion channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns
    (e.g., ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']).

    Usage:

        from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer
    """
    
    def __init__(self, pen_width=1, channel_names=['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'], pen_colors=None,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None,
                 bad_intervals_unix_df: Optional[pd.DataFrame] = None, bad_overlay_alpha: float = 0.9,
                 **kwargs,
                 ):
        """Initialize the motion plot renderer.
        
        Args:
            pen_width: Width of the plot lines (default: 2)
            channel_names: List of channel names to plot (default: ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'])
            pen_colors: Optional list of colors for each channel (default: None, auto-generated)
            bad_intervals_unix_df: Optional DataFrame with columns t_start, t_duration (Unix seconds); vertical dark overlays
            bad_overlay_alpha: Opacity of bad-interval fill (default 0.9 = 90% opaque black)
        """
        ChannelNormalizationModeNormalizingMixin.__init__(self, channel_names=channel_names, fallback_normalization_mode=fallback_normalization_mode, normalization_mode_dict=normalization_mode_dict, arbitrary_bounds=arbitrary_bounds,
                                                         normalize=normalize, normalize_over_full_data=normalize_over_full_data, normalization_reference_df=normalization_reference_df)
        DetailRenderer.__init__(self, **kwargs)


        self.pen_colors = pen_colors
        self.pen_width = pen_width
        self.channel_names = channel_names
        self.bad_intervals_unix_df = bad_intervals_unix_df if bad_intervals_unix_df is not None else pd.DataFrame(columns=['t_start', 't_duration'])
        self.bad_overlay_alpha = float(bad_overlay_alpha)
        # self.fallback_normalization_mode = fallback_normalization_mode
        # self.normalization_mode_dict = normalization_mode_dict
        # self.arbitrary_bounds = arbitrary_bounds

        # Generate distinct colors for each channel
        if (channel_names is not None) and (pen_colors is None):
            # Predefined palette of distinct colors
            color_palette = ['red', 'green', 'blue', 'yellow', 'magenta', 'cyan', 'orange', 'purple']
            # Cycle through palette if more channels than colors
            self.pen_colors = [color_palette[i % len(color_palette)] for i in range(len(channel_names))]
        else:
            self.pen_colors = None

    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render motion data as line plots for each channel.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)

        Usage:
            a_track_name: str = 'MOTION_Epoc X Motion'
            a_renderer = timeline.track_renderers[a_track_name]
            a_detail_renderer = a_renderer.detail_renderer # MotionPlotDetailRenderer 
            a_ds = timeline.track_datasources[a_track_name]
            interval = a_ds.get_overview_intervals()

            dDisplayItem = timeline.ui.dynamic_docked_widget_container.find_display_dock(identifier=a_track_name) # Dock
            a_widget = timeline.ui.matplotlib_view_widgets[a_track_name] # PyqtgraphTimeSynchronizedWidget 
            a_root_graphics_layout_widget = a_widget.getRootGraphicsLayoutWidget()
            a_plot_item = a_widget.getRootPlotItem()

            graphics_objects = a_detail_renderer.render_detail(plot_item=a_plot_item, interval=None, detail_data=a_ds.detailed_df) # List[PlotDataItem]

        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"MotionPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        
        assert (self.channel_names is not None)
        found_channel_names: List[str] = [k for k in self.channel_names if (k in df_sorted.columns)]
        found_all_channel_names: bool = len(found_channel_names) == len(self.channel_names)
        assert found_all_channel_names

        # Filter channels based on visibility if channel_visibility is set
        if hasattr(self, 'channel_visibility') and self.channel_visibility:
            found_channel_names = [ch for ch in found_channel_names if self.channel_visibility.get(ch, True)]

        # Normalize channels using shared helper to support per-group modes
        normalized_channel_df, (y_min, y_max) = self.compute_normalized_channels(detail_df=df_sorted, channel_names=found_channel_names)
        # normalized_channel_df = normalize_channels(df_sorted, found_channel_names, default_mode=self.fallback_normalization_mode, normalization_mode_dict=self.normalization_mode_dict, arbitrary_bounds=self.arbitrary_bounds)

        channel_graphics_items, channel_label_items = self.add_channel_renderables_if_needed(plot_item=plot_item)
        graphics_objects = graphics_objects + channel_graphics_items

        # Extract t_values aligned with normalized_channel_df's index to ensure shape matches
        # normalized_channel_df may have fewer rows due to index intersection during normalization
        t_col_aligned = df_sorted.loc[normalized_channel_df.index, 't']
        if pd.api.types.is_datetime64_any_dtype(t_col_aligned):
            t_values = np.asarray(datetime_to_unix_timestamp(t_col_aligned.to_list()), dtype=float)
        else:
            t_values = t_col_aligned.to_numpy(dtype=float, copy=False)

        # Clamp motion x-values to owning interval bounds (mirrors EEG fix)
        if interval is not None and len(interval) > 0 and 't_start' in interval.columns and 't_duration' in interval.columns and len(t_values) > 0:
            _t_start_raw = interval['t_start'].iloc[0]
            _t_dur = float(interval['t_duration'].iloc[0])
            _t_start_unix = float(datetime_to_unix_timestamp(_t_start_raw)) if isinstance(_t_start_raw, (datetime, pd.Timestamp)) else float(_t_start_raw)
            _t_end_unix = _t_start_unix + _t_dur
            in_interval_mask = np.logical_and(t_values >= _t_start_unix, t_values <= _t_end_unix)
            if np.any(in_interval_mask):
                t_values = t_values[in_interval_mask]
                normalized_channel_df = normalized_channel_df.loc[normalized_channel_df.index[in_interval_mask]]
            elif len(t_values) > 1:
                t_values = np.linspace(_t_start_unix, _t_end_unix, num=len(t_values), endpoint=True)

        if len(t_values) == 0:
            return graphics_objects


        nPlots: int = len(found_channel_names)
        single_channel_height: float = 1.0 / float(nPlots)

        # Plot each channel with its distinct color, grid lines at y_min/y_mid/y_max, and track label
        for i, a_found_channel_name in enumerate(found_channel_names):
            channel_index = self.channel_names.index(a_found_channel_name)
            channel_color = self.pen_colors[channel_index]


            y_values = normalized_channel_df[a_found_channel_name].values
            y_values = y_values * single_channel_height ## scale by the single channel height
            pen = pg.mkPen(channel_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=a_found_channel_name)
            plot_item.addItem(plot_data_item)
            plot_data_item.setPos(0, (float(i)*single_channel_height)) ## position aligned with the channel
            graphics_objects.append(plot_data_item)

        # self._append_bad_interval_regions(plot_item=plot_item, interval=interval, graphics_objects=graphics_objects)
        return graphics_objects


    # def _append_bad_interval_regions(self, plot_item: pg.PlotItem, interval: pd.DataFrame, graphics_objects: List[pg.GraphicsObject]) -> None:
    #     if self.bad_intervals_unix_df is None or len(self.bad_intervals_unix_df) == 0:
    #         return
    #     if interval is None or len(interval) == 0 or 't_start' not in interval.columns or 't_duration' not in interval.columns:
    #         return
    #     _t_start_raw = interval['t_start'].iloc[0]
    #     _t_dur = float(interval['t_duration'].iloc[0])
    #     iv0 = float(datetime_to_unix_timestamp(_t_start_raw)) if isinstance(_t_start_raw, (datetime, pd.Timestamp)) else float(_t_start_raw)
    #     iv1 = iv0 + _t_dur
    #     brush_color = pg.mkColor('black')
    #     brush_color.setAlphaF(self.bad_overlay_alpha)
    #     brush = pg.mkBrush(brush_color)
    #     for row in self.bad_intervals_unix_df.itertuples(index=False):
    #         b0 = float(row.t_start)
    #         b1 = b0 + float(row.t_duration)
    #         x0 = max(b0, iv0)
    #         x1 = min(b1, iv1)
    #         if x1 <= x0:
    #             continue
    #         region = LinearRegionItem(values=(x0, x1), orientation='vertical', brush=brush, movable=False, pen=None)
    #         plot_item.addItem(region)
    #         graphics_objects.append(region)
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove motion plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        if graphics_objects is None:
            return
        conn = getattr(plot_item, '_channel_label_conn', None)
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass
            del plot_item._channel_label_conn
        if getattr(plot_item, '_channel_label_items', None) is not None:
            del plot_item._channel_label_items

        for obj in graphics_objects:
            if obj is None:
                continue
            try:
                plot_item.removeItem(obj)
                if hasattr(obj, 'setParentItem'):
                    obj.setParentItem(None)
            except (AttributeError, RuntimeError):
                # Item may have already been removed or is invalid
                pass

                
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the motion plot.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with motion data (columns: 't' and channel columns)
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) where x is time and y is channel values
        """
        has_valid_detail_data: bool = (detail_data is not None) and isinstance(detail_data, pd.DataFrame) and (len(detail_data) > 0)
        if (interval is None) or (len(interval) == 0):
            # If interval is None or empty, attempt to determine t_start and t_end from detail_data
            if has_valid_detail_data:
                # Try to get time column: use 't' if present, otherwise index values if they look like times
                if 't' in detail_data.columns:
                    t_min = detail_data['t'].min()
                    t_max = detail_data['t'].max()
                    # Convert datetime to Unix timestamp if needed
                    if isinstance(t_min, (datetime, pd.Timestamp)):
                        t_start = datetime_to_unix_timestamp(t_min)
                        t_end = datetime_to_unix_timestamp(t_max)
                    else:
                        t_start = float(t_min)
                        t_end = float(t_max)
                else:
                    # Fallback: use DataFrame index if it is numeric and sorted
                    try:
                        idx = detail_data.index
                        if hasattr(idx, 'dtype') and np.issubdtype(idx.dtype, np.number):
                            t_start = float(idx.min())
                            t_end = float(idx.max())
                        else:
                            t_start = 0.0
                            t_end = 1.0
                    except Exception:
                        t_start = 0.0
                        t_end = 1.0
            else:
                raise ValueError(f'has_valid_detail_data is False')
                # t_start = 0.0
                # t_end = 1.0

            t_duration = t_end - t_start
        else:
            ## interval is provided
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            
            # Handle datetime objects for t_end calculation
            if isinstance(t_start, (datetime, pd.Timestamp)):
                from datetime import timedelta
                t_end = t_start + timedelta(seconds=float(t_duration))
                # Convert to Unix timestamp for return value
                t_start = datetime_to_unix_timestamp(t_start)
                t_end = datetime_to_unix_timestamp(t_end)
            else:
                t_end = t_start + t_duration
        
        # Ensure t_start and t_end are floats (Unix timestamps) for return value
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_start = datetime_to_unix_timestamp(t_start)
        if isinstance(t_end, (datetime, pd.Timestamp)):
            t_end = datetime_to_unix_timestamp(t_end)
        
        if detail_data is None or len(detail_data) == 0:
            return (t_start, t_end, 0.0, 1.0)
        
        if not isinstance(detail_data, pd.DataFrame):
            return (t_start, t_end, 0.0, 1.0)
        
        # Calculate y-axis bounds from all channel values
        assert (self.channel_names is not None)
        # Get all channel columns that exist in the data
        channel_columns = [col for col in self.channel_names if col in detail_data.columns]
        if channel_columns:
            # Find min/max across all channels
            # y_min = min(detail_data[col].min() for col in channel_columns)
            # y_max = max(detail_data[col].max() for col in channel_columns)
            y_min = np.nanmin(np.nanmin(detail_data[col]) for col in channel_columns)
            y_max = np.nanmax(np.nanmax(detail_data[col]) for col in channel_columns)
            # Add padding
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            # Add padding
            y_final_min: float = (y_min - y_pad)
            y_final_max: float = (y_max + y_pad)    
            return (t_start, t_end, y_final_min, y_final_max)

        else:
            # No channels found, use default bounds
            return (t_start, t_end, 0.0, 1.0)


# ==================================================================================================================================================================================================================================================================================== #
# MotionTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #

class MotionTrackDatasource(RawProvidingTrackDatasource):
    """TrackDatasource for motion data with optional LabRecorderXDF / MNE raws (via RawProvidingTrackDatasource).

    Extends RawProvidingTrackDatasource for motion-specific detail rendering and async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.motion import MotionTrackDatasource
    """
    
    def __init__(self, intervals_df: pd.DataFrame, motion_df: pd.DataFrame, custom_datasource_name: Optional[str]=None, max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Dict[str, Tuple[float, float]]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, parent: Optional[QtCore.QObject] = None,
                 bad_intervals_df: Optional[pd.DataFrame] = None, bad_intervals_time_origin_unix: Optional[float] = None,
                 exclude_bad_from_detail: bool = True, bad_overlay_alpha: float = 0.9):
        """Initialize with motion data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            motion_df: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            lab_obj_dict: Map of source id to optional LabRecorderXDF for that file.
            raw_datasets_dict: Map of source id to optional list of MNE Raw objects for that source.
            bad_intervals_df: Optional intervals to mark and optionally exclude (see ``normalize_motion_bad_intervals_df``).
            bad_intervals_time_origin_unix: Required when bad_intervals_df uses MNE ``onset``/``duration`` (recording start, Unix s).
            exclude_bad_from_detail: If True, drop samples whose time falls inside a bad interval before downsampling.
            bad_overlay_alpha: Opacity of bad-interval overlay in the motion detail view (default 0.9).
        """
        if custom_datasource_name is None:
            custom_datasource_name = "MotionTrack"
        super().__init__(intervals_df, detailed_df=motion_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)

        self.fallback_normalization_mode = fallback_normalization_mode
        self.normalization_mode_dict = normalization_mode_dict
        self.arbitrary_bounds = arbitrary_bounds
        self.exclude_bad_from_detail = bool(exclude_bad_from_detail)
        self.bad_overlay_alpha = float(bad_overlay_alpha)
        self._bad_intervals_unix_df: pd.DataFrame = BadMotionDataFrame.normalize_motion_bad_intervals_df(bad_intervals_df, bad_intervals_time_origin_unix)
        self._bad_intervals_key_suffix: str = BadMotionDataFrame.motion_bad_intervals_key_suffix(self._bad_intervals_unix_df)
        self._motion_plot_detail_renderer: Optional[MotionPlotDetailRenderer] = None


    def try_extract_raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[Any]]]]:
        out: Dict[str, Optional[List[Any]]] = {}
        for k, lab in self.lab_obj_dict.items():
            if lab is None or not lab.datasets_dict:
                out[k] = None
                continue
            elst = list(lab.datasets_dict.get(DataModalityType.MOTION, []) or [])
            out[k] = elst if len(elst) > 0 else None
        return out if out else None


    def set_bad_intervals(self, bad_intervals_df: Optional[pd.DataFrame], bad_intervals_time_origin_unix: Optional[float] = None, *, emit_changed: bool = True) -> None:
        """Replace bad/exclusion intervals. Updates the cached detail renderer if present.

        Emits ``source_data_changed_signal`` when ``emit_changed`` is True so the timeline can refresh the track
        overview; for already-added tracks, also replace the track's detail renderer reference if your UI caches it
        (e.g. call ``track_renderer.detail_renderer = datasource.get_detail_renderer()`` after this).
        """
        from phopymnehelper.helpers.dataframe_accessor_helpers import MaskedValidDataFrameAccessor
        from phopymnehelper.motion_data import MotionData, MotionDataFrame, BadMotionDataFrame

        # is_timestamp_format: bool = bad_intervals_df.bad_motion_epochs_df.is_timestamp_format()
        # if is_timestamp_format and (bad_intervals_time_origin_unix is None):
        #     t_unix: float = BadMotionDataFrame._detail_t_column_to_unix_numpy(self.detailed_df['t'])[0]
        #     bad_intervals_time_origin_unix = t_unix

        bad_intervals_df = bad_intervals_df.bad_motion_epochs_df.adding_unix_float_columns(inplace=False)
        # self._bad_intervals_unix_df = self._bad_intervals_unix_df.masked_df.masking_by_intervals(mask_bad_intervals_df=bad_intervals_df, time_col_name='t', bool_mask_column_name='is_bad_motion',
        #                                                             intervals_start_col_name='onset', intervals_end_col_name='onset_end')
        # self._bad_intervals_unix_df.masked_df.add_masking_column(mask_col='is_valid', value_cols=['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'])
        # self._bad_intervals_unix_df
        # masked_detailed_eeg_df: pd.DataFrame = detailed_eeg_df.masked_df.get_masked(copy=True)


        self._bad_intervals_unix_df = BadMotionDataFrame.normalize_motion_bad_intervals_df(bad_intervals_df, bad_intervals_time_origin_unix)
        self._bad_intervals_key_suffix = BadMotionDataFrame.motion_bad_intervals_key_suffix(self._bad_intervals_unix_df)
        if self._motion_plot_detail_renderer is not None:
            self._motion_plot_detail_renderer.bad_intervals_unix_df = self._bad_intervals_unix_df
            self._motion_plot_detail_renderer.bad_overlay_alpha = self.bad_overlay_alpha
        if emit_changed:
            self.source_data_changed_signal.emit()


    # def _post_slice_detailed_dataframe(self, result_df: pd.DataFrame, interval: pd.Series) -> pd.DataFrame:
    #     if not self.exclude_bad_from_detail or len(self._bad_intervals_unix_df) == 0 or len(result_df) == 0:
    #         return result_df
    #     if 't' not in result_df.columns:
    #         return result_df
    #     t_unix = BadMotionDataFrame._detail_t_column_to_unix_numpy(result_df['t'])
    #     bad = np.zeros(len(result_df), dtype=bool)
    #     for row in self._bad_intervals_unix_df.itertuples(index=False):
    #         b0 = float(row.t_start)
    #         b1 = b0 + float(row.t_duration)
    #         bad |= (t_unix >= b0) & (t_unix < b1)
    #     return result_df.loc[~bad].copy()
    

    def get_detail_renderer(self):
        """Get detail renderer for motion data (singleton per datasource so ``set_bad_intervals`` can update overlays)."""
        if self._motion_plot_detail_renderer is None:
            self._motion_plot_detail_renderer = MotionPlotDetailRenderer(
                pen_width=2,
                fallback_normalization_mode=self.fallback_normalization_mode,
                normalization_mode_dict=self.normalization_mode_dict,
                arbitrary_bounds=self.arbitrary_bounds,
                bad_intervals_unix_df=self._bad_intervals_unix_df,
                bad_overlay_alpha=self.bad_overlay_alpha,
            )
        else:
            self._motion_plot_detail_renderer.bad_intervals_unix_df = self._bad_intervals_unix_df
            self._motion_plot_detail_renderer.bad_overlay_alpha = self.bad_overlay_alpha
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
        return self._motion_plot_detail_renderer


    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get cache key for interval (single-row DataFrame or Series); includes suffix when bad intervals affect fetch."""
        base = super().get_detail_cache_key(interval)
        if self.exclude_bad_from_detail and self._bad_intervals_key_suffix:
            return f"{base}_bad{self._bad_intervals_key_suffix}"
        return base


    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: List[pd.DataFrame], custom_datasource_name: Optional[str] = None,
            max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True,
            fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
            bad_intervals_df: Optional[pd.DataFrame] = None, bad_intervals_time_origin_unix: Optional[float] = None, exclude_bad_from_detail: bool = True, bad_overlay_alpha: float = 0.9, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None) -> 'MotionTrackDatasource':
        """Create a MotionTrackDatasource by merging data from multiple sources.
        
        Args:
            intervals_dfs: List of interval DataFrames to merge (each with columns ['t_start', 't_duration'])
            detailed_dfs: List of detailed DataFrames to merge (each with column 't' and motion channel columns)
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            fallback_normalization_mode: Fallback normalization mode for channels
            normalization_mode_dict: Dictionary mapping channel groups to normalization modes
            arbitrary_bounds: Optional dictionary mapping channel names to (min, max) bounds
            bad_intervals_df: Optional bad intervals (``t_start``/``t_duration`` or MNE ``onset``/``duration``).
            bad_intervals_time_origin_unix: Recording start in Unix seconds when using MNE-style onsets.
            exclude_bad_from_detail: Drop samples in bad intervals before downsampling.
            bad_overlay_alpha: Opacity of the dark overlay bands in the detail view.
            lab_obj_dict: Map of source id to optional LabRecorderXDF for that file.
            raw_datasets_dict: Map of source id to optional list of MNE Raw objects for that source.
            
        Returns:
            MotionTrackDatasource instance with merged data
        """
        if not intervals_dfs:
            raise ValueError("intervals_dfs list cannot be empty")
        if not detailed_dfs:
            raise ValueError("detailed_dfs list cannot be empty")
        
        # Merge intervals
        merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start')
        
        # Merge detailed data
        filtered_detailed_dfs = [df for df in detailed_dfs if df is not None and len(df) > 0]
        if not filtered_detailed_dfs:
            raise ValueError("No valid detailed DataFrames provided")
        merged_detailed_df = pd.concat(filtered_detailed_dfs, ignore_index=True).sort_values('t')
        
        # Create instance with merged data
        return cls(
            intervals_df=merged_intervals_df,
            motion_df=merged_detailed_df,
            custom_datasource_name=custom_datasource_name,
            max_points_per_second=max_points_per_second,
            enable_downsampling=enable_downsampling,
            fallback_normalization_mode=fallback_normalization_mode,
            normalization_mode_dict=normalization_mode_dict,
            arbitrary_bounds=arbitrary_bounds,
            bad_intervals_df=bad_intervals_df,
            bad_intervals_time_origin_unix=bad_intervals_time_origin_unix,
            exclude_bad_from_detail=exclude_bad_from_detail,
            bad_overlay_alpha=bad_overlay_alpha,
            lab_obj_dict=lab_obj_dict,
            raw_datasets_dict=raw_datasets_dict,
        )


__all__ = ['MotionPlotDetailRenderer', 'MotionTrackDatasource', 'normalize_motion_bad_intervals_df', 'motion_bad_intervals_key_suffix']

