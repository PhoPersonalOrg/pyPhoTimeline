from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from qtpy import QtCore
from typing import Dict, List, Mapping, Tuple, Optional, Callable, Union, Any, Sequence, TYPE_CHECKING, cast
from datetime import datetime
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, RawProvidingTrackDatasource, ComputableDatasourceMixin
if TYPE_CHECKING:
    import mne
    import phopymnehelper.type_aliases as types
    from phopymnehelper.xdf_files import LabRecorderXDF
    from pypho_timeline.timeline_builder import TimelineBuilder
    from pypho_timeline.widgets.simple_timeline_widget import SimpleTimelineWidget

from phopymnehelper.analysis.computations.eeg_registry import run_eeg_computations_graph, session_fingerprint_for_raw_or_path
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp

from pypho_timeline.utils.logging_util import get_rendering_logger
logger = get_rendering_logger(__name__)

from dose_analysis_python.DoseCurveCalculation.pysb_pkpd_da_ne_monoamine import PySbPKPD_DA_NE_DoseCurveModel
from dose_analysis_python.FileImportExport.DoseImporter import DoseNoteFragmentParser


# ==================================================================================================================================================================================================================================================================================== #
# DosePlotDetailRenderer - Renders eeg data as line plots.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #
import pyqtgraph as pg

from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer


## NOTE: Currently inherits directly from DetailRenderer protocol. GenericPlotDetailRenderer is designed
## to wrap functions rather than for traditional inheritance. MotionPlotDetailRenderer follows the same pattern.
class DosePlotDetailRenderer(DataframePlotDetailRenderer):
    """Detail renderer for eeg tracks that displays eeg channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns
    (e.g., ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']).

    Usage:
        from pypho_timeline.rendering.datasources.specific.eeg import DosePlotDetailRenderer, DoseTrackDatasource, SpectrogramChannelGroupConfig



    """
    
    def __init__(self, channel_names: Optional[List[str]]=None, text_color='orange', text_size=10, text_rotation=90, y_position=0.0, anchor=(0.5, 0.5), line_color=None, line_width=1, enable_lines=True):
        """Initialize the text log plot renderer.
        
        Args:
            channel_names: Optional list of channel names to display. If None, defaults to ['message'] (default: None)
            text_color: Color for text labels (default: 'white')
            text_size: Font size in points (default: 10)
            text_rotation: Rotation angle in degrees (default: 90 for vertical)
            y_position: Y-coordinate for text placement (default: 0.5)
            anchor: Text anchor point as (x, y) tuple (default: (0, 0.5) for left-center)  A value of (0,0) sets the upper-left corner of the text box to be at the position specified by setPos(), while a value of (1,1) sets the lower-right corner.
            line_color: Color for vertical lines. If None, defaults to text_color (default: None)
            line_width: Width of vertical lines in pixels (default: 1)
            enable_lines: Whether to draw vertical lines at message times (default: True)
        """
        if channel_names is None:
            channel_names = ['msg'] # ['message']

        # Initialize parent with minimal params to skip line plotting logic
        super().__init__(pen_width=1, channel_names=channel_names, normalize=False)
        self.text_color = text_color
        self.text_size = text_size
        self.text_rotation = text_rotation
        self.y_position = y_position
        self.anchor = anchor
        self.line_color = line_color if line_color is not None else text_color
        self.line_width = line_width
        self.enable_lines = enable_lines
        self.active_model = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=None, quanta=None, max_events=1200, follow_h_after_last=24))

    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render eeg data as line plots for each channel.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)

        Usage:
            a_track_name: str = 'MOTION_Epoc X Dose'
            a_renderer = timeline.track_renderers[a_track_name]
            a_detail_renderer = a_renderer.detail_renderer # DosePlotDetailRenderer 
            a_ds = timeline.track_datasources[a_track_name]
            interval = a_ds.get_overview_intervals()

            dDisplayItem = timeline.ui.dynamic_docked_widget_container.find_display_dock(identifier=a_track_name) # Dock
            a_widget = timeline.ui.matplotlib_view_widgets[a_track_name] # PyqtgraphTimeSynchronizedWidget 
            a_root_graphics_layout_widget = a_widget.getRootGraphicsLayoutWidget()
            a_plot_item = a_widget.getRootPlotItem()

            graphics_objects = a_detail_renderer.render_detail(plot_item=a_plot_item, interval=None, detail_data=a_ds.detailed_df) # List[PlotDataItem]

        """
        logger.debug(f"DosePlotDetailRenderer[].render_detail(plot_item: {plot_item},\n\tinterval='{interval}',\n\t detail_data={detail_data}) - starting")
    
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"DosePlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns:
            return []
        
        # Determine which channel columns to use
        channel_names_to_use = self.channel_names
        if channel_names_to_use is None:
            # Auto-detect: all non-numeric columns except 't'
            non_numeric_cols = detail_data.select_dtypes(exclude=[np.number]).columns.tolist()
            channel_names_to_use = [col for col in non_numeric_cols if col != 't']
            if len(channel_names_to_use) == 0:
                return []  # No channels found
        else:
            # Use explicitly provided channel names
            found_channel_names: List[str] = [k for k in channel_names_to_use if (k in detail_data.columns)]
            # Only assert all channels required when channel_names was explicitly provided
            found_all_channel_names: bool = len(found_channel_names) == len(channel_names_to_use)
            if not found_all_channel_names:
                missing_channels = set(channel_names_to_use) - set(found_channel_names)
                raise ValueError(f"Missing channels: {missing_channels}")
            channel_names_to_use = found_channel_names
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')

        # # Compute interval bounds as unix seconds so we can clamp log events
        # interval_t_start_unix: Optional[float] = None
        # interval_t_end_unix: Optional[float] = None
        # if interval is not None and len(interval) > 0 and 't_start' in interval.columns and 't_duration' in interval.columns:
        #     from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
        #     _t_start_raw = interval['t_start'].iloc[0]
        #     _t_dur = float(interval['t_duration'].iloc[0])
        #     interval_t_start_unix = float(datetime_to_unix_timestamp(_t_start_raw)) if isinstance(_t_start_raw, (datetime, pd.Timestamp)) else float(_t_start_raw)
        #     interval_t_end_unix = interval_t_start_unix + _t_dur


        from dose_analysis_python.DoseCurveCalculation.pysb_pkpd_da_ne_monoamine import PySbPKPD_DA_NE_DoseCurveModel
        from dose_analysis_python.FileImportExport.DoseImporter import DoseNoteFragmentParser


        self.active_model = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, max_events=120, follow_h_after_last=24)
        curve_dict = active_model.compute()
        fig = active_model.plot()

        message = " | ".join(text_parts)
        txt_df = df_sorted[['t', *channel_names_to_use]] ## just the ['t', 'msg'] columns
        txt_df.str.

        potential_note_strings_to_parse: List[str] = []
        # Create a TextItem for each row, displaying all channel values
        for idx, row in df_sorted.iterrows():
            t_value = float(row['t'])

            # # Skip events that fall outside the owning interval bounds
            # if interval_t_start_unix is not None and interval_t_end_unix is not None:
            #     if t_value < interval_t_start_unix or t_value > interval_t_end_unix:
            #         continue
            
            # Create vertical line at message time if enabled
            if self.enable_lines:
                vline = pg.InfiniteLine(angle=90, movable=False, pos=t_value)
                vline.setPen(pg.mkPen(color=self.line_color, width=self.line_width))
                vline.setZValue(-10)  # Render lines behind text labels
                plot_item.addItem(vline, ignoreBounds=True)
                graphics_objects.append(vline)
            
            # Combine all channel values into a single text string
            text_parts = []
            for channel_name in channel_names_to_use:
                channel_value = str(row[channel_name])
                if len(channel_names_to_use) > 1:
                    text_parts.append(f"{channel_name}: {channel_value}")
                else:
                    text_parts.append(channel_value)
            
            message = " | ".join(text_parts)
            potential_note_strings_to_parse.append(message)

            # Create text item
            text_item = pg.TextItem(
                text=message,
                color=self.text_color,
                anchor=self.anchor
            )
            
            # Set font size
            font = text_item.textItem.font()
            font.setPointSize(self.text_size)
            text_item.textItem.setFont(font)
            
            # Set position
            text_item.setPos(t_value, self.y_position)
            
            # Set rotation if needed
            if self.text_rotation != 0:
                text_item.setRotation(self.text_rotation)
            
            # Add to plot
            plot_item.addItem(text_item)
            graphics_objects.append(text_item)
        
        ## try to parase
        potential_note_to_try_parse: str = '\n'.join(potential_note_strings_to_parse)
        logger.info(f"potential_note_to_try_parse: '''\n{potential_note_to_try_parse}'''\n")
        parsed_record_df, parsed_records_dict, (parsed_quanta, parsed_quanta_dict) = DoseNoteFragmentParser.parse_dose_note(test_note=potential_note_to_try_parse)
        if (len(parsed_record_df) > 0) and (len(parsed_quanta) > 0):
            logger.warning(f"\tafter parsing len(parsed_record_df): {len(parsed_record_df)}\n\tlen(parsed_quanta): {len(parsed_quanta)}.\n\t Building model...")
            self.active_model = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, **self.active_model.parameters)
            logger.warning(f"\tafter building model: computing...")
            curve_dict = self.active_model.compute()
            fig = self.active_model.plot()

        else:
            logger.warning(f"\tafter parsing len(parsed_record_df) or len(parsed_quanta) == 0")



        return graphics_objects
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove eeg plot graphics objects.
        
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
        """Get bounds for the eeg plot.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with eeg data (columns: 't' and channel columns)
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) where x is time and y is channel values
        """
        has_valid_detail_data: bool = (detail_data is not None) and isinstance(detail_data, pd.DataFrame) and (len(detail_data) > 0)
        if (interval is None) or (len(interval) == 0):
            # If interval is None or empty, attempt to determine t_start and t_end from detail_data
            if has_valid_detail_data:
                # Try to get time column: use 't' if present
                if 't' in detail_data.columns:
                    t_start = float(detail_data['t'].min())
                    t_end = float(detail_data['t'].max())
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
                from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                t_start = datetime_to_unix_timestamp(t_start)
                t_end = datetime_to_unix_timestamp(t_end)
            else:
                t_end = t_start + t_duration
        
        # Ensure t_start and t_end are floats (Unix timestamps) for return value
        if isinstance(t_start, (datetime, pd.Timestamp)):
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            t_start = datetime_to_unix_timestamp(t_start)
        if isinstance(t_end, (datetime, pd.Timestamp)):
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            t_end = datetime_to_unix_timestamp(t_end)
        
        # Text logs don't have numeric y-values, so use fixed y-bounds
        return (t_start, t_end, 0.0, 1.0)


# ==================================================================================================================================================================================================================================================================================== #
# DoseTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #
# class DoseTrackDatasource(ComputableDatasourceMixin, DataframePlotDetailRenderer):
#     """TrackDatasource for Dose data with optional LabRecorderXDF / MNE raws (via RawProvidingTrackDatasource).

#     Extends RawProvidingTrackDatasource for eeg-specific detail rendering and async detail loading.

#     Usage:

#         from pypho_timeline.rendering.datasources.specific.eeg import DoseTrackDatasource
#     """
#     sigSourceComputeStarted = QtCore.Signal()
#     sigSourceComputeFinished = QtCore.Signal(bool)

#     def __init__(self, intervals_df: pd.DataFrame, eeg_df: pd.DataFrame, custom_datasource_name: Optional[str]=None,
#                  max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
#                  fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
#                  normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
#                  arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
#                  normalize: bool = True, normalize_over_full_data: bool = True,
#                  normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, parent: Optional[QtCore.QObject] = None,
#                  plot_pen_colors: Optional[List[str]] = None, plot_pen_width: Optional[float] = None,
#                  ):
#         """Initialize with eeg data and intervals.
        
#         Args:
#             intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
#             eeg_df: DataFrame with columns ['t'] and channel columns (e.g., ['AF3', 'F7', 'F3', ...])
#             custom_datasource_name: Custom name for this datasource (optional)
#             max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
#             enable_downsampling: Whether to enable downsampling. Default: True
#             plot_pen_colors: Optional per-channel line colors for :class:`DosePlotDetailRenderer` (default: auto palette).
#             plot_pen_width: Optional line width for :class:`DosePlotDetailRenderer` (default: same as renderer default used here, 2).
#         """
#         if custom_datasource_name is None:
#             custom_datasource_name = "DoseTrack"
#         super().__init__(intervals_df, detailed_df=eeg_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)

#         if (normalization_reference_df is None) and (self.detailed_df is not None):
#             normalization_reference_df = self.detailed_df

#         # self._detail_renderer = DosePlotDetailRenderer(
#         #         pen_width=2,
#         #         fallback_normalization_mode=fallback_normalization_mode,
#         #         normalization_mode_dict=normalization_mode_dict,
#         #         arbitrary_bounds=arbitrary_bounds,
#         #         normalize=normalize,
#         #         normalize_over_full_data=normalize_over_full_data,
#         #         normalization_reference_df=normalization_reference_df,
#         #     )

#         self.fallback_normalization_mode = fallback_normalization_mode
#         self.normalization_mode_dict = normalization_mode_dict
#         self.arbitrary_bounds = arbitrary_bounds
#         self.normalize = normalize
#         self.normalization_mode_dict = normalization_mode_dict
#         self.arbitrary_bounds = arbitrary_bounds
#         self.normalize_over_full_data = normalize_over_full_data
#         self.normalization_reference_df = normalization_reference_df
#         self.channel_names = channel_names
#         self.plot_pen_colors = plot_pen_colors
#         self.plot_pen_width = plot_pen_width

#         self.ComputableDatasourceMixin_on_init()
#         self.clear_computed_result()

#         # Override visualization properties (parent sets blue, we want blue too, but keep same height)
#         # Parent already sets series_height=1.0, which is what we want, so no change needed
#         # Parent already sets blue color, which is what we want, so no change needed


#     @property
#     def num_sessions(self) -> int:
#         """The num_sessions property."""
#         return len(self.intervals_df)



#     def try_extract_raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[Any]]]]:
#         if not self.lab_obj_dict:
#             return None
#         from phopymnehelper.SavedSessionsProcessor import DataModalityType
#         from phopymnehelper.MNE_helpers import up_convert_raw_objects
#         from phopymnehelper.Dose_data import DoseData
#         out: Dict[str, Optional[List[Any]]] = {}
#         for k, lab in self.lab_obj_dict.items():
#             if lab is None or not lab.datasets_dict:
#                 out[k] = None
#                 continue
#             elst = list(lab.datasets_dict.get(DataModalityType.Dose.value, []) or [])
#             out[k] = up_convert_raw_objects(elst) if len(elst) > 0 else None
#         if not out:
#             return None
#         _all_eeg_for_montage = [r for _lst in out.values() if _lst for r in _lst]
#         if len(_all_eeg_for_montage) > 0:
#             DoseData.set_montage(datasets_Dose=_all_eeg_for_montage)
#         return cast(Dict[str, Optional[List[Any]]], self._sort_raws_by_meas_start(out))


#     def get_detail_renderer(self):
#         """Get detail renderer for eeg data."""
#         _extra_kw = {'channel_names': self.channel_names} if self.channel_names is not None else {}
#         if self.plot_pen_colors is not None:
#             _extra_kw['pen_colors'] = self.plot_pen_colors
#         _pen_width = 2 if self.plot_pen_width is None else self.plot_pen_width
#         if self.detailed_df is None:
#             print(f'WARN: self.detailed_df is None!')
#         return DosePlotDetailRenderer(pen_width=_pen_width, fallback_normalization_mode=self.fallback_normalization_mode, normalization_mode_dict=self.normalization_mode_dict, arbitrary_bounds=self.arbitrary_bounds, normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df, **_extra_kw)



#     def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
#         """Get cache key for interval (single-row DataFrame or Series)."""
#         return super().get_detail_cache_key(interval)


#     @function_attributes(short_name=None, tags=['MAIN'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2026-03-02 04:23', related_items=[])
#     @classmethod
#     def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: List[pd.DataFrame], custom_datasource_name: Optional[str] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True,
#                                    fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None,
#                                    lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None,
#         **kwargs) -> 'DoseTrackDatasource':
#         """Create an DoseTrackDatasource by merging data from multiple sources.
        
#         Args:
#             intervals_dfs: List of interval DataFrames to merge (each with columns ['t_start', 't_duration'])
#             detailed_dfs: List of detailed DataFrames to merge (each with column 't' and Dose channel columns)
#             custom_datasource_name: Custom name for this datasource (optional)
#             max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
#             enable_downsampling: Whether to enable downsampling. Default: True
#             fallback_normalization_mode: Fallback normalization mode for channels
#             normalization_mode_dict: Dictionary mapping channel groups to normalization modes
#             arbitrary_bounds: Optional dictionary mapping channel names to (min, max) bounds
#             normalize: Whether to normalize channels. Default: True
#             normalize_over_full_data: Whether to normalize over full dataset. Default: True
#             normalization_reference_df: Optional reference DataFrame for normalization
            
#         Returns:
#             DoseTrackDatasource instance with merged data
#         """
#         if not intervals_dfs:
#             raise ValueError("intervals_dfs list cannot be empty")
#         if not detailed_dfs:
#             raise ValueError("detailed_dfs list cannot be empty")
        
#         # Merge intervals
#         merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start')
        
#         # Merge detailed data
#         filtered_detailed_dfs = [df for df in detailed_dfs if df is not None and len(df) > 0]
#         if not filtered_detailed_dfs:
#             raise ValueError("No valid detailed DataFrames provided")
#         merged_detailed_df = pd.concat(filtered_detailed_dfs, ignore_index=True).sort_values('t')
        
#         # Use merged data as normalization reference if not provided
#         if normalization_reference_df is None:
#             normalization_reference_df = merged_detailed_df
        
#         # Create instance with merged data
#         return cls(
#             intervals_df=merged_intervals_df,
#             eeg_df=merged_detailed_df,
#             custom_datasource_name=custom_datasource_name,
#             max_points_per_second=max_points_per_second,
#             enable_downsampling=enable_downsampling,
#             fallback_normalization_mode=fallback_normalization_mode,
#             normalization_mode_dict=normalization_mode_dict,
#             arbitrary_bounds=arbitrary_bounds,
#             normalize=normalize,
#             normalize_over_full_data=normalize_over_full_data,
#             normalization_reference_df=normalization_reference_df,
#             channel_names=channel_names,
#             lab_obj_dict=lab_obj_dict,
#             raw_datasets_dict=raw_datasets_dict,
#         )


#     # ==================================================================================================================================================================================================================================================================================== #
#     # ComputableDatasourceMixin Conformance                                                                                                                                                                                                                                                #
#     # ==================================================================================================================================================================================================================================================================================== #
#     def compute(self, **kwargs):
#         """ a function to perform recomputation of the datasource properties at runtime 
#         """
#         logger.info(f'.compute(...) called.')
#         if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
#             if self.parent() is not None:
#                 if getattr(self.parent(), 'raw_datasets_dict', None) is not None:
#                     self.raw_datasets_dict = self.parent().raw_datasets_dict


#         self.clear_computed_result()
#         self.sigSourceComputeStarted.emit()




#         active_model: PySbPKPD_DA_NE_DoseCurveModel = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, max_events=120, follow_h_after_last=24)
#         curve_dict = active_model.compute()
#         fig = active_model.plot()


#         active_compute_goals_list = ("time_independent_bad_channels", "bad_epochs", "spectogram")

#         ## init the compute list goals
#         for a_specific_computed_goal_name in active_compute_goals_list:
#             if a_specific_computed_goal_name not in self.computed_result:
#                 self.computed_result[a_specific_computed_goal_name] = [] ## create a list


#         raws = self.get_sorted_and_extracted_raws(self.raw_datasets_dict)
#         for eeg_raw in raws:
#             if eeg_raw is not None:
#                 eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=active_compute_goals_list)
#                 for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
#                     if a_specific_computed_value is not None:
#                         if a_specific_computed_goal_name not in self.computed_result:
#                             self.computed_result[a_specific_computed_goal_name] = []
#                         self.computed_result[a_specific_computed_goal_name].append(a_specific_computed_value)

#         ## END for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items()...

#         ## OUTPUTS: eeg_comps_flat_concat_dict
#         self.on_compute_finished()


#     def clear_computed_result(self):
#         print(f'clear_computed_result()')
#         self.computed_result.clear()
#         ## reset
#         self.merged_bad_epoch_intervals_df = None
#         self.merged_bad_epoch_intervals_plot_callback_fn = None


#     def on_compute_finished(self, **kwargs):
#         """ called to indicate that a recompute is finished """
#         was_success: bool = (self.computed_result is not None) and (len(self.computed_result) > 0) # (self._spectrogram_result is not None)
#         logger.info(f'.on_compute_finished(was_success: {was_success})')
#         eeg_comps_flat_concat_dict = self.computed_result


#         # eeg_comps_flat_concat_dict = self.extract_all_datasets_results(eeg_comps_results_dict=self.computed_result)

#         eeg_comps_flat_concat_dict = self.computed_result.copy()
#         if 'bad_epochs' in eeg_comps_flat_concat_dict:
#             ## tries to provide keys: eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']

#             def _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict) -> pd.DataFrame:
#                 """ computes the bad epoch times for Dose/MOTION tracks and optinally adds them to the timeline to preview 

#                     eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

#                 """
#                 ## INPUTS: eeg_ds, eeg_comps_flat_concat_dict
#                 ## UPDATES: eeg_comps_flat_concat_dict
#                 # bad_epochs_intervals_df_t_col_names: str = ['start_t', 'end_t']
#                 bad_epochs_intervals_df_t_col_names: str = ['t_start', 't_end']
#                 bad_epochs_intervals_df_non_descript_rel_t_col_names = [f'{a_t_col}_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

#                 bad_epochs_intervals_df_sess_rel_t_col_names = [f'{a_t_col}_sess_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]
#                 bad_epochs_intervals_df_timeline_rel_t_col_names = [f'{a_t_col}_timeline_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

#                 # active_col_names = ['t_start', 't_start_dt', 't_end', 't_end_dt', 't_duration'] ## if allowing native datetime-based columns:
#                 active_col_names = ['t_start', 't_end', 't_duration'] ## if allowing native datetime-based columns:

#                 rename_fn = lambda df: df.rename(columns=dict(zip(['start_t', 'end_t', 'start_t_rel', 'end_t_rel', 'start_t_dt', 'end_t_dt', 'duration'], ['t_start', 't_end', 't_start_rel', 't_end_rel', 't_start_dt', 't_end_dt', 't_duration'])), inplace=False)

#                 ds_overview_intervals_df: pd.DataFrame = eeg_ds.get_overview_intervals()[active_col_names].sort_values(active_col_names).reset_index(drop=True)

#                 for idx, a_bad_epochs_result_dict in enumerate(eeg_comps_flat_concat_dict['bad_epochs']):
#                     active_interval_row = ds_overview_intervals_df.iloc[idx].to_dict()
#                     active_interval_t_start: float = active_interval_row['t_start']
#                     a_bad_epochs_df = a_bad_epochs_result_dict.get('bad_epoch_intervals_df', None)
#                     # a_bad_epochs_df = a_bad_epochs_result_dict.pop('bad_epoch_intervals_df', None)
#                     if a_bad_epochs_df is not None:
#                         a_bad_epochs_df = rename_fn(a_bad_epochs_df)
#                         print(f'idx: {idx}, active_interval_t_start: {active_interval_t_start}, {active_interval_row}:')
#                         for a_t_col in bad_epochs_intervals_df_t_col_names:
#                             a_bad_epochs_df[a_t_col] = a_bad_epochs_df[f'{a_t_col}_rel'] + active_interval_t_start ## these are relative to each individual session/recording, not the timeline start or the earliest recording
                            
#                         a_bad_epochs_df['eeg_raw_idx'] = idx
#                         a_bad_epochs_result_dict['bad_epoch_intervals_df'] = a_bad_epochs_df ## re-apply

#                 # [v.get('bad_epoch_intervals_df', None) for idx, v in enumerate(eeg_comps_flat_concat_dict['bad_epochs'])]
#                 merged_bad_epoch_intervals_df: pd.DataFrame = pd.concat([v.get('bad_epoch_intervals_df', None) for v in eeg_comps_flat_concat_dict['bad_epochs']])
#                 # merged_bad_epoch_intervals_df
#                 merged_bad_epoch_intervals_df = rename_fn(merged_bad_epoch_intervals_df)
#                 earliest_interval_t_start: float = np.nanmin(ds_overview_intervals_df['t_start'].to_numpy())
#                 merged_bad_epoch_intervals_df[bad_epochs_intervals_df_timeline_rel_t_col_names] = merged_bad_epoch_intervals_df[bad_epochs_intervals_df_t_col_names] - earliest_interval_t_start ## timeline start relative
#                 merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df.rename(columns=dict(zip(bad_epochs_intervals_df_non_descript_rel_t_col_names, bad_epochs_intervals_df_sess_rel_t_col_names)), inplace=False) ## indicate that the non-descript '*_rel' columns are actually '*_sess_rel' columns
#                 merged_bad_epoch_intervals_df

#                 # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df'] = merged_bad_epoch_intervals_df
#                 eeg_ds.merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df

#                 ## OUTPUTS: merged_bad_epoch_intervals_df
#                 return eeg_comps_flat_concat_dict
#             ## END def _subfn_post_compute_build_merged_bad_epochs(e....
            
#             def _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds, timeline, include_overlays_on_timeline_tracks: bool=True, include_dedicated_interval_track: bool=False) -> pd.DataFrame:
#                 """ plots the bad epochs on the Dose/MOTION views and optionally as a separate track

#                     a_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(timeline=timeline, eeg_ds=eeg_ds, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
#                 """
#                 from phopymnehelper.analysis.computations.specific.bad_epochs import ensure_bad_epochs_interval_track, apply_bad_epochs_overlays_to_timeline

#                 # assert eeg_comps_flat_concat_dict is not None
#                 # merged_bad_epoch_intervals_df: pd.DataFrame = eeg_comps_flat_concat_dict.get('merged_bad_epoch_intervals_df', None)

#                 merged_bad_epoch_intervals_df: pd.DataFrame = eeg_ds.merged_bad_epoch_intervals_df.copy()
#                 # assert merged_bad_epoch_intervals_df is not None

#                 if merged_bad_epoch_intervals_df is None:
#                     print(f'WARNING: {merged_bad_epoch_intervals_df} is None!')
#                     return None

#                 #TODO 2026-04-03 08:57: - [ ] needs timeline `timeline`
#                 _common_kwargs = dict(time_offset=0)

#                 if include_overlays_on_timeline_tracks:
#                     new_regions = apply_bad_epochs_overlays_to_timeline(timeline, merged_bad_epoch_intervals_df, add_interval_track=include_dedicated_interval_track, **_common_kwargs)


#                 if include_dedicated_interval_track:
#                     ensure_bad_epochs_interval_track(timeline, merged_bad_epoch_intervals_df, **_common_kwargs)

#                 return merged_bad_epoch_intervals_df


#             ## reset
#             self.merged_bad_epoch_intervals_df = None
#             self.merged_bad_epoch_intervals_plot_callback_fn = None
            
#             eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(self, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict) ## sets `eeg_ds.merged_bad_epoch_intervals_df`, doesn't change `eeg_comps_flat_concat_dict`

#             # merged_bad_epoch_intervals_plot_callback_fn = lambda eeg_ds, timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=eeg_ds, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)

#             ## this version captures `self`
#             merged_bad_epoch_intervals_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=self, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)

#             # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_plot_callback_fn'] = merged_bad_epoch_intervals_plot_callback_fn
#             # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']
#             self.merged_bad_epoch_intervals_plot_callback_fn = merged_bad_epoch_intervals_plot_callback_fn

#             # ## USAGE:
#             #     eeg_ds.merged_bad_epoch_intervals_plot_callback_fn(timeline=timeline, include_overlays_on_timeline_tracks=True)



#         # for a_specific_computed_goal_name, a_specific_computed_value_list in eeg_comps_flat_concat_dict.items():
#         #     for a_specific_computed_value in (a_specific_computed_value_list or []):
#         #         if a_specific_computed_value is not None:
#         #             ## do the post-compute stuff
#         #             if a_specific_computed_goal_name == 'bad_epochs': # in eeg_comps_flat_concat_dict:
#         #                 ## tries to provide keys: eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']

#         #                 def _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict) -> pd.DataFrame:
#         #                     """ computes the bad epoch times for Dose/MOTION tracks and optinally adds them to the timeline to preview 

#         #                         eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

#         #                     """
#         #                     ## INPUTS: eeg_ds, eeg_comps_flat_concat_dict
#         #                     ## UPDATES: eeg_comps_flat_concat_dict
#         #                     # bad_epochs_intervals_df_t_col_names: str = ['start_t', 'end_t']
#         #                     bad_epochs_intervals_df_t_col_names: str = ['t_start', 't_end']
#         #                     bad_epochs_intervals_df_non_descript_rel_t_col_names = [f'{a_t_col}_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

#         #                     bad_epochs_intervals_df_sess_rel_t_col_names = [f'{a_t_col}_sess_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]
#         #                     bad_epochs_intervals_df_timeline_rel_t_col_names = [f'{a_t_col}_timeline_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

#         #                     active_col_names = ['t_start', 't_start_dt', 't_end', 't_end_dt', 't_duration']
#         #                     rename_fn = lambda df: df.rename(columns=dict(zip(['start_t', 'end_t', 'start_t_rel', 'end_t_rel', 'start_t_dt', 'end_t_dt', 'duration'], ['t_start', 't_end', 't_start_rel', 't_end_rel', 't_start_dt', 't_end_dt', 't_duration'])), inplace=False)

#         #                     ds_overview_intervals_df: pd.DataFrame = eeg_ds.get_overview_intervals()[active_col_names].sort_values(active_col_names).reset_index(drop=True)

#         #                     for idx, a_bad_epochs_result_dict in enumerate(eeg_comps_flat_concat_dict['bad_epochs']):
#         #                         active_interval_row = ds_overview_intervals_df.iloc[idx].to_dict()
#         #                         active_interval_t_start: float = active_interval_row['t_start']
#         #                         a_bad_epochs_df = a_bad_epochs_result_dict.get('bad_epoch_intervals_df', None)
#         #                         # a_bad_epochs_df = a_bad_epochs_result_dict.pop('bad_epoch_intervals_df', None)
#         #                         if a_bad_epochs_df is not None:
#         #                             a_bad_epochs_df = rename_fn(a_bad_epochs_df)
#         #                             print(f'idx: {idx}, active_interval_t_start: {active_interval_t_start}, {active_interval_row}:')
#         #                             for a_t_col in bad_epochs_intervals_df_t_col_names:
#         #                                 a_bad_epochs_df[a_t_col] = a_bad_epochs_df[f'{a_t_col}_rel'] + active_interval_t_start ## these are relative to each individual session/recording, not the timeline start or the earliest recording
                                        
#         #                             a_bad_epochs_df['eeg_raw_idx'] = idx
#         #                             a_bad_epochs_result_dict['bad_epoch_intervals_df'] = a_bad_epochs_df ## re-apply

#         #                     # [v.get('bad_epoch_intervals_df', None) for idx, v in enumerate(eeg_comps_flat_concat_dict['bad_epochs'])]
#         #                     merged_bad_epoch_intervals_df: pd.DataFrame = pd.concat([v.get('bad_epoch_intervals_df', None) for v in eeg_comps_flat_concat_dict['bad_epochs']])
#         #                     # merged_bad_epoch_intervals_df
#         #                     merged_bad_epoch_intervals_df = rename_fn(merged_bad_epoch_intervals_df)
#         #                     earliest_interval_t_start: float = np.nanmin(ds_overview_intervals_df['t_start'].to_numpy())
#         #                     merged_bad_epoch_intervals_df[bad_epochs_intervals_df_timeline_rel_t_col_names] = merged_bad_epoch_intervals_df[bad_epochs_intervals_df_t_col_names] - earliest_interval_t_start ## timeline start relative
#         #                     merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df.rename(columns=dict(zip(bad_epochs_intervals_df_non_descript_rel_t_col_names, bad_epochs_intervals_df_sess_rel_t_col_names)), inplace=False) ## indicate that the non-descript '*_rel' columns are actually '*_sess_rel' columns
#         #                     merged_bad_epoch_intervals_df

#         #                     # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df'] = merged_bad_epoch_intervals_df
#         #                     eeg_ds.merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df

#         #                     ## OUTPUTS: merged_bad_epoch_intervals_df
#         #                     return eeg_comps_flat_concat_dict
#         #                 ## END def _subfn_post_compute_build_merged_bad_epochs(e....
                        
#         #                 def _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict, timeline, include_overlays_on_timeline_tracks: bool=True, include_dedicated_interval_track: bool=False) -> pd.DataFrame:
#         #                     """ plots the bad epochs on the Dose/MOTION views and optionally as a separate track

#         #                         a_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(timeline=timeline, eeg_ds=eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
#         #                     """
#         #                     from phopymnehelper.analysis.computations.specific.bad_epochs import ensure_bad_epochs_interval_track, apply_bad_epochs_overlays_to_timeline

#         #                     assert eeg_comps_flat_concat_dict is not None
#         #                     merged_bad_epoch_intervals_df: pd.DataFrame = eeg_comps_flat_concat_dict.get('merged_bad_epoch_intervals_df', None)

#         #                     if merged_bad_epoch_intervals_df is None:
#         #                         print(f'WARNING: {merged_bad_epoch_intervals_df} is None!')
#         #                         return None

#         #                     #TODO 2026-04-03 08:57: - [ ] needs timeline `timeline`
#         #                     _common_kwargs = dict(time_offset=0)

#         #                     if include_overlays_on_timeline_tracks:
#         #                         new_regions = apply_bad_epochs_overlays_to_timeline(timeline, merged_bad_epoch_intervals_df, add_interval_track=include_dedicated_interval_track, **_common_kwargs)


#         #                     if include_dedicated_interval_track:
#         #                         ensure_bad_epochs_interval_track(timeline, merged_bad_epoch_intervals_df, **_common_kwargs)

#         #                     return merged_bad_epoch_intervals_df


#         #                 ## reset
#         #                 self.merged_bad_epoch_intervals_df = None
#         #                 self.merged_bad_epoch_intervals_plot_callback_fn = None
                        
#         #                 eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(self, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

#         #                 merged_bad_epoch_intervals_plot_callback_fn = lambda eeg_ds, timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
#         #                 # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_plot_callback_fn'] = merged_bad_epoch_intervals_plot_callback_fn
#         #                 # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']
#         #                 self.merged_bad_epoch_intervals_plot_callback_fn = merged_bad_epoch_intervals_plot_callback_fn

#         #                 # ## USAGE:
#         #                 #     eeg_ds.merged_bad_epoch_intervals_plot_callback_fn(timeline=timeline, include_overlays_on_timeline_tracks=True)




#         self.sigSourceComputeFinished.emit(was_success)


#     def get_computed_results_for_sess(self, sess_idx: int) -> Dict[types.DoseComputationId, Dict[str, Any]]:
#         """ gets the results filtered for only the single session

#         Usage:

#             desired_sess_idx: int = (eeg_ds.num_sessions - 1) ## last session
#             filtered_computed_result: Dict[types.DoseComputationId, Dict[str, Any]] = eeg_ds.get_computed_results_for_sess(sess_idx=desired_sess_idx)
#             filtered_computed_result

#         """
#         assert (sess_idx < self.num_sessions), f"sess_idx: {sess_idx} but max allowed index is (self.num_sessions - 1): {(self.num_sessions - 1)}"
#         # computed_result: Dict[types.DoseComputationId, List[Dict[str, Any]]] = self.computed_result # Each list has one entry per eeg_sess
#         filtered_computed_result: Dict[types.DoseComputationId, Dict[str, Any]] = {k:v[sess_idx] for k, v in self.computed_result.items()} ## filtered for only the single session
#         return filtered_computed_result


#     def add_spectrogram_tracks_for_channel_groups(self, spectrogram_channel_groups: Optional[List[SpectrogramChannelGroupConfig]], timeline: "SimpleTimelineWidget", timeline_builder: "TimelineBuilder", *, update_time_range: bool = False, skip_existing_names: bool = True) -> List["DoseSpectrogramTrackDatasource"]:
#         """Compute interval-aligned spectrograms from raws, create one ``DoseSpectrogramTrackDatasource`` child per channel group (shared STFT, differing ``group_config``), and append tracks via ``timeline_builder.update_timeline``.

#         When ``spectrogram_channel_groups`` is None or empty, adds a single spectrogram track (all channels averaged). Names use prefix ``Dose_Spectrogram_<suffix>`` so dock grouping matches ``stream_to_datasources``.
#         """
#         if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
#             if self.parent() is not None and getattr(self.parent(), "raw_datasets_dict", None) is not None:
#                 self.raw_datasets_dict = self.parent().raw_datasets_dict
#         if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
#             logger.warning("add_spectrogram_tracks_for_channel_groups: no raws in raw_datasets_dict for %s; skipping.", self.custom_datasource_name)
#             return []
#         spec_results = compute_multiraw_spectrogram_results(self.intervals_df, self.raw_datasets_dict)
#         name_prefix = _eeg_parent_spectrogram_track_name_prefix(self.custom_datasource_name)
#         _effective_groups: Optional[List[SpectrogramChannelGroupConfig]] = spectrogram_channel_groups if (spectrogram_channel_groups is not None and len(spectrogram_channel_groups) > 0) else None
#         specs: List[Tuple[str, Optional[SpectrogramChannelGroupConfig], Optional[List[SpectrogramChannelGroupConfig]]]] = []
#         if _effective_groups is None:
#             specs.append((name_prefix, None, None))
#         else:
#             for group_cfg in _effective_groups:
#                 specs.append((f"{name_prefix}_{group_cfg.name}", SpectrogramChannelGroupConfig(name=group_cfg.name, channels=list(group_cfg.channels)), _effective_groups))
#         created: List[Any] = []
#         for track_name, gcfg, presets in specs:
#             if skip_existing_names and track_name in timeline.track_datasources:
#                 logger.debug("add_spectrogram_tracks_for_channel_groups: skip existing track %r", track_name)
#                 continue
#             child: DoseSpectrogramTrackDatasource = DoseSpectrogramTrackDatasource(intervals_df=self.intervals_df.copy(), spectrogram_result=None, spectrogram_results=spec_results, custom_datasource_name=track_name, group_config=gcfg, channel_group_presets=presets, lab_obj_dict=self.lab_obj_dict, raw_datasets_dict=self.raw_datasets_dict, parent=self)
#             created.append(child)
#         if getattr(self, "_spectrogram_child_datasources", None) is None:
#             self._spectrogram_child_datasources = []
#         self._spectrogram_child_datasources.extend(created)
#         if len(created) > 0:
#             timeline_builder.update_timeline(timeline, [*created], update_time_range=update_time_range)
#         return created



__all__ = ['DosePlotDetailRenderer'] # , 'DoseTrackDatasource'

