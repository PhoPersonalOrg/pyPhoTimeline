from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from qtpy import QtCore
from typing import Dict, List, Mapping, Tuple, Optional, Callable, Union, Any, Sequence, TYPE_CHECKING, cast
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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
from phopymnehelper.MNE_helpers import MNEHelpers
from phopylslhelper.datetime_helpers import to_display_timezone, unix_timestamp_to_datetime, float_to_datetime
from datetime import datetime, timedelta
from dose_analysis_python.Helpers.quantization import Quanta, ComputationTimeBlock


from pypho_timeline import SynchronizedPlotMode
from pypho_timeline.rendering.helpers import ChannelNormalizationMode
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer


# ==================================================================================================================================================================================================================================================================================== #
# DosePlotDetailRenderer - Renders EventBoard doses + dose curves.                                                                                                                                                                                                                     #
# ==================================================================================================================================================================================================================================================================================== #
import pyqtgraph as pg

from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer


EVENTBOARD_TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_CURVE_KEYS = ["AMPH_blood", "DA_str", "NE_pfc"]
DEFAULT_CURVE_COLORS = ["#4FC3F7", "#FFB74D", "#81C784", "#BA68C8"]


class DosePlotDetailRenderer(LogTextDataFramePlotDetailRenderer):
    """Detail renderer for EventBoard dose records with pyqtgraph dose curves."""

    def __init__(self, channel_names: Optional[List[str]]=None, text_color='orange', text_size=10, text_rotation=90, y_position=0.0, anchor=(0.5, 0.5), line_color=None, line_width=1, enable_lines=True, curve_keys: Optional[List[str]]=None, curve_pen_colors: Optional[List[str]]=None, curve_pen_width: float=2.0, max_events: int=120, follow_h_after_last: float=24.0, backend: str='scipy'):
        if channel_names is None:
            channel_names = ['msg']
        super().__init__(channel_names=channel_names, text_color=text_color, text_size=text_size, text_rotation=text_rotation, y_position=y_position, anchor=anchor, line_color=line_color, line_width=line_width, enable_lines=enable_lines)
        self.base_y_position = y_position
        self.curve_keys = list(curve_keys) if curve_keys is not None else list(DEFAULT_CURVE_KEYS)
        self.curve_pen_colors = list(curve_pen_colors) if curve_pen_colors is not None else list(DEFAULT_CURVE_COLORS)
        self.curve_pen_width = curve_pen_width
        self.max_events = max_events
        self.follow_h_after_last = follow_h_after_last
        self.backend = backend
        self.active_model = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=pd.DataFrame(), quanta=pd.Series(dtype=float), parameters={'backend': backend}, max_events=max_events, follow_h_after_last=follow_h_after_last)
        self._last_curve_payload: Optional[Dict[str, Any]] = None


    def _get_channel_names_to_use(self, detail_data: pd.DataFrame) -> List[str]:
        channel_names_to_use = self.channel_names
        if channel_names_to_use is None:
            non_numeric_cols = detail_data.select_dtypes(exclude=['number']).columns.tolist()
            channel_names_to_use = [col for col in non_numeric_cols if col != 't']
            if len(channel_names_to_use) == 0:
                return []
            return channel_names_to_use
        found_channel_names: List[str] = [k for k in channel_names_to_use if (k in detail_data.columns)]
        found_all_channel_names: bool = len(found_channel_names) == len(channel_names_to_use)
        if not found_all_channel_names:
            missing_channels = set(channel_names_to_use) - set(found_channel_names)
            raise ValueError(f"Missing channels: {missing_channels}")
        return found_channel_names


    def _build_message_from_row(self, row: pd.Series, channel_names_to_use: List[str]) -> str:
        text_parts: List[str] = []
        for channel_name in channel_names_to_use:
            channel_value = str(row[channel_name])
            if len(channel_names_to_use) > 1:
                text_parts.append(f"{channel_name}: {channel_value}")
            else:
                text_parts.append(channel_value)
        return " | ".join(text_parts).strip()


    def _build_daily_note_dict(self, detail_data: pd.DataFrame) -> Dict[datetime, str]:
        channel_names_to_use = self._get_channel_names_to_use(detail_data)
        if len(channel_names_to_use) == 0:
            return {}
        grouped_lines: Dict[datetime, List[str]] = {}
        for _, row in detail_data.sort_values('t').iterrows():
            raw_t_value = row['t']
            try:
                t_value = float(raw_t_value)
            except (TypeError, ValueError):
                continue
            message = self._build_message_from_row(row=row, channel_names_to_use=channel_names_to_use)
            if len(message) == 0:
                continue
            try:
                DoseNoteFragmentParser.parse_numeric_dose([message])
            except Exception:
                continue
            local_dt = datetime.fromtimestamp(float(t_value), tz=timezone.utc).astimezone(EVENTBOARD_TIMEZONE)
            note_day = datetime(local_dt.year, local_dt.month, local_dt.day)
            time_text = local_dt.strftime('%I:%M%p').lstrip('0').lower()
            grouped_lines.setdefault(note_day, []).append(f"{time_text} - {message}")
        return {day: '\n'.join(lines) for day, lines in grouped_lines.items() if len(lines) > 0}


    def _compute_curve_payload(self, detail_data: Any) -> Optional[Dict[str, Any]]:
        self._last_curve_payload = None
        if detail_data is None or len(detail_data) == 0:
            return None
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"DosePlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        if 't' not in detail_data.columns:
            return None
        daily_note_dict = self._build_daily_note_dict(detail_data=detail_data)
        if len(daily_note_dict) == 0:
            return None
        try:
            parse_result = cast(Any, DoseNoteFragmentParser.parse_dose_note(test_note=daily_note_dict))
            parsed_record_df, _, (parsed_quanta, _) = parse_result
        except Exception as e:
            logger.warning("DosePlotDetailRenderer parse failed: %s", e)
            return None
        parsed_record_df = cast(pd.DataFrame, parsed_record_df)
        parsed_quanta = cast(pd.Series, parsed_quanta)
        if (len(parsed_record_df) == 0) or (len(parsed_quanta) == 0):
            return None
        try:
            self.active_model = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, parameters={'backend': self.backend}, max_events=self.max_events, follow_h_after_last=self.follow_h_after_last)
            curve_dict = self.active_model.compute()
        except Exception as e:
            logger.warning("DosePlotDetailRenderer compute failed: %s", e)
            return None
        meta = curve_dict.get('meta', None)
        y_dict = curve_dict.get('y_dict', None)
        t_h = np.asarray(curve_dict.get('t_h', []), dtype=float)
        if (meta is None) or (y_dict is None) or (len(y_dict) == 0) or (t_h.size == 0):
            return None
        t0 = meta.get('t0', None)
        if t0 is None:
            return None
        try:
            if isinstance(t0, pd.Timestamp):
                t0_dt = t0.to_pydatetime()
            elif isinstance(t0, datetime):
                t0_dt = t0
            elif isinstance(t0, str):
                t0_dt = pd.Timestamp(t0).to_pydatetime()
            else:
                return None
            t0_unix_raw = datetime_to_unix_timestamp(t0_dt)
            if isinstance(t0_unix_raw, list):
                return None
            t0_unix = float(t0_unix_raw)
        except Exception:
            return None
        selected_curve_keys = [k for k in self.curve_keys if k in y_dict]
        if len(selected_curve_keys) == 0:
            selected_curve_keys = list(y_dict.keys())[:3]
        curve_arrays: Dict[str, np.ndarray] = {}
        for key in selected_curve_keys:
            y_values = np.asarray(cast(Any, y_dict[key]), dtype=float)
            if y_values.shape == t_h.shape:
                curve_arrays[key] = y_values
        if len(curve_arrays) == 0:
            return None
        finite_blocks = [values[np.isfinite(values)] for values in curve_arrays.values() if np.any(np.isfinite(values))]
        if len(finite_blocks) == 0:
            return None
        finite_values = np.concatenate(finite_blocks)
        curve_min = float(np.nanmin(finite_values))
        curve_max = float(np.nanmax(finite_values))
        curve_range = max(curve_max - curve_min, 1.0)
        curve_padding = max(curve_range * 0.08, 0.5)
        text_y_position = max(self.base_y_position, curve_max + curve_padding)
        payload = {'curve_dict': curve_dict, 'curve_arrays': curve_arrays, 'curve_min': curve_min, 'curve_max': curve_max, 'curve_padding': curve_padding, 'text_y_position': text_y_position, 't_x': t0_unix + (t_h * 3600.0)}
        self._last_curve_payload = payload
        return payload


    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        logger.debug(f"DosePlotDetailRenderer[].render_detail(plot_item: {plot_item},\n\tinterval='{interval}',\n\t detail_data={detail_data}) - starting")
        curve_payload = self._compute_curve_payload(detail_data=detail_data)
        original_y_position = self.y_position
        self.y_position = self.base_y_position if curve_payload is None else curve_payload['text_y_position']
        try:
            graphics_objects = super().render_detail(plot_item=plot_item, interval=interval, detail_data=detail_data)
        finally:
            self.y_position = original_y_position
        if curve_payload is None:
            return graphics_objects
        for idx, (curve_key, y_values) in enumerate(curve_payload['curve_arrays'].items()):
            curve_item = pg.PlotDataItem(curve_payload['t_x'], y_values, pen=pg.mkPen(color=self.curve_pen_colors[idx % len(self.curve_pen_colors)], width=self.curve_pen_width), name=curve_key)
            plot_item.addItem(curve_item)
            graphics_objects.append(curve_item)
        return graphics_objects
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove eeg plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        if graphics_objects is None:
            return
        plot_item_any = cast(Any, plot_item)
        conn = getattr(plot_item_any, '_channel_label_conn', None)
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass
            del plot_item_any._channel_label_conn
        if getattr(plot_item_any, '_channel_label_items', None) is not None:
            del plot_item_any._channel_label_items

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
        x_min, x_max, _, _ = super().get_detail_bounds(interval=interval, detail_data=detail_data)
        curve_payload = self._compute_curve_payload(detail_data=detail_data)
        if curve_payload is None:
            return (x_min, x_max, 0.0, 1.0)
        curve_x = np.asarray(curve_payload['t_x'], dtype=float)
        if curve_x.size > 0:
            x_min = min(x_min, float(np.nanmin(curve_x)))
            x_max = max(x_max, float(np.nanmax(curve_x)))
        y_min = min(0.0, curve_payload['curve_min'] - curve_payload['curve_padding'])
        y_max = max(1.0, curve_payload['text_y_position'] + curve_payload['curve_padding'])
        return (x_min, x_max, y_min, y_max)


# ==================================================================================================================================================================================================================================================================================== #
# DoseTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #
class DoseTrackDatasource(ComputableDatasourceMixin, DataframePlotDetailRenderer):
    """TrackDatasource for Dose data with optional LabRecorderXDF / MNE raws (via RawProvidingTrackDatasource).

    Extends RawProvidingTrackDatasource for eeg-specific detail rendering and async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.dose import DosePlotDetailRenderer, DoseTrackDatasource

        dose_curve_ds: DoseTrackDatasource = DoseTrackDatasource.init_from_timeline_text_log_tracks(timeline=timeline)
        dose_curve_ds



    """
    sigSourceComputeStarted = QtCore.Signal()
    sigSourceComputeFinished = QtCore.Signal(bool)

    def __init__(self, intervals_df: pd.DataFrame, recordSeries_df: pd.DataFrame, complete_curve_df: pd.DataFrame, custom_datasource_name: Optional[str]=None,
                 max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, parent: Optional[QtCore.QObject] = None,
                 plot_pen_colors: Optional[List[str]] = None, plot_pen_width: Optional[float] = None,
                 ):
        """Initialize with eeg data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            eeg_df: DataFrame with columns ['t'] and channel columns (e.g., ['AF3', 'F7', 'F3', ...])
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            plot_pen_colors: Optional per-channel line colors for :class:`DosePlotDetailRenderer` (default: auto palette).
            plot_pen_width: Optional line width for :class:`DosePlotDetailRenderer` (default: same as renderer default used here, 2).
        """
        if custom_datasource_name is None:
            custom_datasource_name = "DoseTrack"
        super().__init__(intervals_df, detailed_df=complete_curve_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)
        self.recordSeries_df = recordSeries_df

        if (normalization_reference_df is None) and (self.detailed_df is not None):
            normalization_reference_df = self.detailed_df

        # self._detail_renderer = DosePlotDetailRenderer(
        #         pen_width=2,
        #         fallback_normalization_mode=fallback_normalization_mode,
        #         normalization_mode_dict=normalization_mode_dict,
        #         arbitrary_bounds=arbitrary_bounds,
        #         normalize=normalize,
        #         normalize_over_full_data=normalize_over_full_data,
        #         normalization_reference_df=normalization_reference_df,
        #     )

        self.fallback_normalization_mode = fallback_normalization_mode
        self.normalization_mode_dict = normalization_mode_dict
        self.arbitrary_bounds = arbitrary_bounds
        self.normalize = normalize
        self.normalization_mode_dict = normalization_mode_dict
        self.arbitrary_bounds = arbitrary_bounds
        self.normalize_over_full_data = normalize_over_full_data
        self.normalization_reference_df = normalization_reference_df
        self.channel_names = channel_names
        self.plot_pen_colors = plot_pen_colors
        self.plot_pen_width = plot_pen_width

        self.ComputableDatasourceMixin_on_init()
        self.clear_computed_result()

        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed


    @classmethod
    def _perform_parse_message_logs_to_dose_events(cls, detailed_txt_log_df):
        """ Parse message logs for dose-like entries 
        """
        ## INPUTS: detailed_txt_log_df
        # detailed_txt_log_df['msg']
        # detailed_txt_log_df 

        # r'\d+\s*\.?\s*\d*\s*plus'

        # dose_event_pattern = r'\d+\s*\.?\s*\d*\s*plus'
        # matching_rows = detailed_txt_log_df[detailed_txt_log_df['msg'].astype(str).str.contains(dose_event_pattern, regex=True, na=False)]
        # matching_rows

        dose_event_pattern = r'(\d+\s*\.?\s*\d*)\s*plus'

        matched_with_quantity = (
            detailed_txt_log_df.loc[detailed_txt_log_df['msg'].astype(str).str.contains(dose_event_pattern, regex=True, na=False), ['msg']]
            .assign(quantity=lambda df: df['msg'].astype(str).str.extract(dose_event_pattern, expand=False).str.replace(r'\s+', '', regex=True))
        )

        matched_with_quantity

        # matched_with_quantity['dt']

        # a_parsed_dose_record = DoseNoteFragmentParser.parse_numeric_dose([a_parsed_dose])[0]

        parsed_dose_records_dict: Dict[pd.Timestamp, Dict] = dict(zip(matched_with_quantity.index.to_list(), DoseNoteFragmentParser.parse_numeric_dose(matched_with_quantity['quantity'].to_list())))
        parsed_dose_records_dict
        ## OUTPUTS: parsed_dose_records_dict


        ## build records
        default_med_name: str='AMPH'
        recordSeries_df: pd.DataFrame = pd.DataFrame({'recordDoseDate': list(parsed_dose_records_dict.keys()), 
                                                    'recordDoseValue': [a_dose_record_dict['value'] for k, a_dose_record_dict in parsed_dose_records_dict.items()],
                                                    'modifier': [a_dose_record_dict.get('modifier', '') for k, a_dose_record_dict in parsed_dose_records_dict.items()],
                                })
        recordSeries_df = recordSeries_df.set_index('recordDoseDate', drop=True, inplace=False)
        # recordSeries.index = pd.DatetimeIndex(recordSeries.index).tz_localize("US/Eastern")
        recordSeries_df.index = pd.DatetimeIndex(recordSeries_df.index).tz_convert("US/Eastern")
        recordSeries_df['medication'] = default_med_name
        ## OUTPUTS: recordSeries_df
        return recordSeries_df


    @classmethod
    def init_from_timeline_text_log_tracks(cls, timeline) -> "DoseTrackDatasource":
        """ only implemented init function """

        all_track_names = timeline.get_all_track_names()
        print(f"all_track_names: {all_track_names}")
        txt_log_widget, txt_log_renderer, txt_log_ds = timeline.get_track_tuple('LOG_TextLogger')
        txt_log_ds

        detailed_txt_log_df: pd.DataFrame = deepcopy(txt_log_ds.detailed_df).reset_index(drop=True) #.set_index('t')

        if 'dt' not in detailed_txt_log_df.columns:
            detailed_txt_log_df['dt'] = float_to_datetime(detailed_txt_log_df['t'].to_numpy(), reference_datetime=timeline.reference_datetime)

        detailed_txt_log_df = detailed_txt_log_df.set_index('dt', drop=False, inplace=False)
        ## OUTPUTS: detailed_txt_log_df
        detailed_txt_log_df


        ## INPUTS: detailed_txt_log_df
        recordSeries_df = cls._perform_parse_message_logs_to_dose_events(detailed_txt_log_df)
        recordSeries_df

        ## INPUTS: timeline, recordSeries_df
        # def build_dose_curve_track(timeline, recordSeries_df):
        ## compute specific datetime windows by passing the initial/final state vector to the calculation
        start_date: datetime = timeline.total_data_start_time # datetime(2026, 4, 13)
        # end_date: Optional[datetime] = None
        end_date: Optional[datetime] = timeline.total_data_end_time

        computation_blocks, complete_curve_df = ComputationTimeBlock.init_from_start_end_date(parsed_record_df=recordSeries_df, start_date=start_date, end_date=end_date)
        ## OUTPUTS: computation_blocks, complete_curve_df
        # print(list(complete_curve_df.columns)) # ['t_h', 'AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf', 'DA_str', 'NE_pfc', 'DA_pfc', 'compute_block_idx', 't']


        ## INPUTS: complete_curve_df
        ## time_column_names = ['t_h', 't']
        curve_channel_names = [col for col in ['AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf', 'DA_str', 'NE_pfc', 'DA_pfc'] if col in complete_curve_df.columns]
        curve_df = complete_curve_df[['t'] + curve_channel_names].copy()
        interval_start = curve_df['t'].min()
        interval_duration_seconds = (curve_df['t'].max() - interval_start).total_seconds()
        intervals_df = pd.DataFrame({'t_start': [interval_start], 't_duration': [interval_duration_seconds]})
        curve_renderer = DataframePlotDetailRenderer(channel_names=curve_channel_names, normalize=True, 
                                                    normalization_mode_dict={
                ('AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf'): ChannelNormalizationMode.GROUPMINMAXRANGE,
                ('DA_str', 'DA_pfc'): ChannelNormalizationMode.GROUPMINMAXRANGE,
                ('NE_pfc',): ChannelNormalizationMode.GROUPMINMAXRANGE,
            }, fallback_normalization_mode = ChannelNormalizationMode.INDIVIDUAL,
            pen_width=1.5,
        )

        ## INPUTS: complete_curve_df, recordSeries_df

        # dose_curve_ds = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=curve_df, custom_datasource_name=track_name, detail_renderer=curve_renderer, enable_downsampling=False)
        dose_curve_ds = cls(intervals_df=intervals_df, recordSeries_df=recordSeries_df, complete_curve_df=complete_curve_df, custom_datasource_name=track_name, detail_renderer=curve_renderer, enable_downsampling=False)

        return dose_curve_ds




    @classmethod
    def build_dose_curve_track(cls, timeline, complete_curve_df: pd.DataFrame, track_name = 'DOSE_CURVES_Computed'):
        ## INPUTS: complete_curve_df
        ## time_column_names = ['t_h', 't']
        curve_channel_names = [col for col in ['AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf', 'DA_str', 'NE_pfc', 'DA_pfc'] if col in complete_curve_df.columns]
        curve_df = complete_curve_df[['t'] + curve_channel_names].copy()
        interval_start = curve_df['t'].min()
        interval_duration_seconds = (curve_df['t'].max() - interval_start).total_seconds()
        intervals_df = pd.DataFrame({'t_start': [interval_start], 't_duration': [interval_duration_seconds]})
        curve_renderer = DataframePlotDetailRenderer(channel_names=curve_channel_names, normalize=True, 
                                                    normalization_mode_dict={
                ('AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf'): ChannelNormalizationMode.GROUPMINMAXRANGE,
                ('DA_str', 'DA_pfc'): ChannelNormalizationMode.GROUPMINMAXRANGE,
                ('NE_pfc',): ChannelNormalizationMode.GROUPMINMAXRANGE,
            }, fallback_normalization_mode = ChannelNormalizationMode.INDIVIDUAL,
            pen_width=1.5,
        )

        dose_curve_ds = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=curve_df, custom_datasource_name=track_name, detail_renderer=curve_renderer, enable_downsampling=False)

        if track_name in timeline.get_all_track_names():
            print(f"Track '{track_name}' already exists; skipping add.")
        else:
            track_widget, root_graphics, plot_item, dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(name=track_name, dockSize=(500, 120), dockAddLocationOpts=['bottom'], sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA)
            timeline.add_track(dose_curve_ds, name=track_name, plot_item=plot_item)

        
        return dose_curve_ds, curve_renderer


    @property
    def num_sessions(self) -> int:
        """The num_sessions property."""
        return len(self.intervals_df)



    def try_extract_raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[Any]]]]:
        if not self.lab_obj_dict:
            return None
        from phopymnehelper.SavedSessionsProcessor import DataModalityType
        from phopymnehelper.MNE_helpers import up_convert_raw_objects
        from phopymnehelper.Dose_data import DoseData
        out: Dict[str, Optional[List[Any]]] = {}
        for k, lab in self.lab_obj_dict.items():
            if lab is None or not lab.datasets_dict:
                out[k] = None
                continue
            elst = list(lab.datasets_dict.get(DataModalityType.Dose.value, []) or [])
            out[k] = up_convert_raw_objects(elst) if len(elst) > 0 else None
        if not out:
            return None
        _all_eeg_for_montage = [r for _lst in out.values() if _lst for r in _lst]
        if len(_all_eeg_for_montage) > 0:
            DoseData.set_montage(datasets_Dose=_all_eeg_for_montage)
        return cast(Dict[str, Optional[List[Any]]], self._sort_raws_by_meas_start(out))


    def get_detail_renderer(self):
        """Get detail renderer for eeg data."""
        _extra_kw = {'channel_names': self.channel_names} if self.channel_names is not None else {}
        if self.plot_pen_colors is not None:
            _extra_kw['pen_colors'] = self.plot_pen_colors
        _pen_width = 2 if self.plot_pen_width is None else self.plot_pen_width
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
        return DosePlotDetailRenderer(pen_width=_pen_width, fallback_normalization_mode=self.fallback_normalization_mode, normalization_mode_dict=self.normalization_mode_dict, arbitrary_bounds=self.arbitrary_bounds, normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df, **_extra_kw)



    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get cache key for interval (single-row DataFrame or Series)."""
        return super().get_detail_cache_key(interval)


    # @classmethod
    # def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: List[pd.DataFrame], custom_datasource_name: Optional[str] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True,
    #                                fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None,
    #                                lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None,
    #     **kwargs) -> 'DoseTrackDatasource':
    #     """Create an DoseTrackDatasource by merging data from multiple sources.
        
    #     Args:
    #         intervals_dfs: List of interval DataFrames to merge (each with columns ['t_start', 't_duration'])
    #         detailed_dfs: List of detailed DataFrames to merge (each with column 't' and Dose channel columns)
    #         custom_datasource_name: Custom name for this datasource (optional)
    #         max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
    #         enable_downsampling: Whether to enable downsampling. Default: True
    #         fallback_normalization_mode: Fallback normalization mode for channels
    #         normalization_mode_dict: Dictionary mapping channel groups to normalization modes
    #         arbitrary_bounds: Optional dictionary mapping channel names to (min, max) bounds
    #         normalize: Whether to normalize channels. Default: True
    #         normalize_over_full_data: Whether to normalize over full dataset. Default: True
    #         normalization_reference_df: Optional reference DataFrame for normalization
            
    #     Returns:
    #         DoseTrackDatasource instance with merged data
    #     """
    #     if not intervals_dfs:
    #         raise ValueError("intervals_dfs list cannot be empty")
    #     if not detailed_dfs:
    #         raise ValueError("detailed_dfs list cannot be empty")
        
    #     # Merge intervals
    #     merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start')
        
    #     # Merge detailed data
    #     filtered_detailed_dfs = [df for df in detailed_dfs if df is not None and len(df) > 0]
    #     if not filtered_detailed_dfs:
    #         raise ValueError("No valid detailed DataFrames provided")
    #     merged_detailed_df = pd.concat(filtered_detailed_dfs, ignore_index=True).sort_values('t')
        
    #     # Use merged data as normalization reference if not provided
    #     if normalization_reference_df is None:
    #         normalization_reference_df = merged_detailed_df
        
    #     # Create instance with merged data
    #     return cls(
    #         intervals_df=merged_intervals_df,
    #         eeg_df=merged_detailed_df,
    #         custom_datasource_name=custom_datasource_name,
    #         max_points_per_second=max_points_per_second,
    #         enable_downsampling=enable_downsampling,
    #         fallback_normalization_mode=fallback_normalization_mode,
    #         normalization_mode_dict=normalization_mode_dict,
    #         arbitrary_bounds=arbitrary_bounds,
    #         normalize=normalize,
    #         normalize_over_full_data=normalize_over_full_data,
    #         normalization_reference_df=normalization_reference_df,
    #         channel_names=channel_names,
    #         lab_obj_dict=lab_obj_dict,
    #         raw_datasets_dict=raw_datasets_dict,
    #     )


    # ==================================================================================================================================================================================================================================================================================== #
    # ComputableDatasourceMixin Conformance                                                                                                                                                                                                                                                #
    # ==================================================================================================================================================================================================================================================================================== #
    def compute(self, **kwargs):
        """ a function to perform recomputation of the datasource properties at runtime 
        """
        logger.info(f'.compute(...) called.')
        if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
            if self.parent() is not None:
                if getattr(self.parent(), 'raw_datasets_dict', None) is not None:
                    self.raw_datasets_dict = self.parent().raw_datasets_dict


        self.clear_computed_result()
        self.sigSourceComputeStarted.emit()




        active_model: PySbPKPD_DA_NE_DoseCurveModel = PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, max_events=120, follow_h_after_last=24)
        curve_dict = active_model.compute()
        fig = active_model.plot()


        active_compute_goals_list = ("time_independent_bad_channels", "bad_epochs", "spectogram")

        ## init the compute list goals
        for a_specific_computed_goal_name in active_compute_goals_list:
            if a_specific_computed_goal_name not in self.computed_result:
                self.computed_result[a_specific_computed_goal_name] = [] ## create a list


        raws = self.get_sorted_and_extracted_raws(self.raw_datasets_dict)
        for eeg_raw in raws:
            if eeg_raw is not None:
                eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=active_compute_goals_list)
                for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
                    if a_specific_computed_value is not None:
                        if a_specific_computed_goal_name not in self.computed_result:
                            self.computed_result[a_specific_computed_goal_name] = []
                        self.computed_result[a_specific_computed_goal_name].append(a_specific_computed_value)

        ## END for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items()...

        ## OUTPUTS: eeg_comps_flat_concat_dict
        self.on_compute_finished()


    def clear_computed_result(self):
        print(f'clear_computed_result()')
        self.computed_result.clear()
        ## reset
        self.merged_bad_epoch_intervals_df = None
        self.merged_bad_epoch_intervals_plot_callback_fn = None


    def on_compute_finished(self, **kwargs):
        """ called to indicate that a recompute is finished """
        was_success: bool = (self.computed_result is not None) and (len(self.computed_result) > 0) # (self._spectrogram_result is not None)
        logger.info(f'.on_compute_finished(was_success: {was_success})')
        eeg_comps_flat_concat_dict = self.computed_result


        # eeg_comps_flat_concat_dict = self.extract_all_datasets_results(eeg_comps_results_dict=self.computed_result)

        eeg_comps_flat_concat_dict = self.computed_result.copy()
        if 'bad_epochs' in eeg_comps_flat_concat_dict:
            ## tries to provide keys: eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']

            def _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict) -> pd.DataFrame:
                """ computes the bad epoch times for Dose/MOTION tracks and optinally adds them to the timeline to preview 

                    eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

                """
                ## INPUTS: eeg_ds, eeg_comps_flat_concat_dict
                ## UPDATES: eeg_comps_flat_concat_dict
                # bad_epochs_intervals_df_t_col_names: str = ['start_t', 'end_t']
                bad_epochs_intervals_df_t_col_names: str = ['t_start', 't_end']
                bad_epochs_intervals_df_non_descript_rel_t_col_names = [f'{a_t_col}_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

                bad_epochs_intervals_df_sess_rel_t_col_names = [f'{a_t_col}_sess_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]
                bad_epochs_intervals_df_timeline_rel_t_col_names = [f'{a_t_col}_timeline_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

                # active_col_names = ['t_start', 't_start_dt', 't_end', 't_end_dt', 't_duration'] ## if allowing native datetime-based columns:
                active_col_names = ['t_start', 't_end', 't_duration'] ## if allowing native datetime-based columns:

                rename_fn = lambda df: df.rename(columns=dict(zip(['start_t', 'end_t', 'start_t_rel', 'end_t_rel', 'start_t_dt', 'end_t_dt', 'duration'], ['t_start', 't_end', 't_start_rel', 't_end_rel', 't_start_dt', 't_end_dt', 't_duration'])), inplace=False)

                ds_overview_intervals_df: pd.DataFrame = eeg_ds.get_overview_intervals()[active_col_names].sort_values(active_col_names).reset_index(drop=True)

                for idx, a_bad_epochs_result_dict in enumerate(eeg_comps_flat_concat_dict['bad_epochs']):
                    active_interval_row = ds_overview_intervals_df.iloc[idx].to_dict()
                    active_interval_t_start: float = active_interval_row['t_start']
                    a_bad_epochs_df = a_bad_epochs_result_dict.get('bad_epoch_intervals_df', None)
                    # a_bad_epochs_df = a_bad_epochs_result_dict.pop('bad_epoch_intervals_df', None)
                    if a_bad_epochs_df is not None:
                        a_bad_epochs_df = rename_fn(a_bad_epochs_df)
                        print(f'idx: {idx}, active_interval_t_start: {active_interval_t_start}, {active_interval_row}:')
                        for a_t_col in bad_epochs_intervals_df_t_col_names:
                            a_bad_epochs_df[a_t_col] = a_bad_epochs_df[f'{a_t_col}_rel'] + active_interval_t_start ## these are relative to each individual session/recording, not the timeline start or the earliest recording
                            
                        a_bad_epochs_df['eeg_raw_idx'] = idx
                        a_bad_epochs_result_dict['bad_epoch_intervals_df'] = a_bad_epochs_df ## re-apply

                # [v.get('bad_epoch_intervals_df', None) for idx, v in enumerate(eeg_comps_flat_concat_dict['bad_epochs'])]
                merged_bad_epoch_intervals_df: pd.DataFrame = pd.concat([v.get('bad_epoch_intervals_df', None) for v in eeg_comps_flat_concat_dict['bad_epochs']])
                # merged_bad_epoch_intervals_df
                merged_bad_epoch_intervals_df = rename_fn(merged_bad_epoch_intervals_df)
                earliest_interval_t_start: float = np.nanmin(ds_overview_intervals_df['t_start'].to_numpy())
                merged_bad_epoch_intervals_df[bad_epochs_intervals_df_timeline_rel_t_col_names] = merged_bad_epoch_intervals_df[bad_epochs_intervals_df_t_col_names] - earliest_interval_t_start ## timeline start relative
                merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df.rename(columns=dict(zip(bad_epochs_intervals_df_non_descript_rel_t_col_names, bad_epochs_intervals_df_sess_rel_t_col_names)), inplace=False) ## indicate that the non-descript '*_rel' columns are actually '*_sess_rel' columns
                merged_bad_epoch_intervals_df

                # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df'] = merged_bad_epoch_intervals_df
                eeg_ds.merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df

                ## OUTPUTS: merged_bad_epoch_intervals_df
                return eeg_comps_flat_concat_dict
            ## END def _subfn_post_compute_build_merged_bad_epochs(e....
            
            def _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds, timeline, include_overlays_on_timeline_tracks: bool=True, include_dedicated_interval_track: bool=False) -> pd.DataFrame:
                """ plots the bad epochs on the Dose/MOTION views and optionally as a separate track

                    a_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(timeline=timeline, eeg_ds=eeg_ds, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
                """
                from phopymnehelper.analysis.computations.specific.bad_epochs import ensure_bad_epochs_interval_track, apply_bad_epochs_overlays_to_timeline

                # assert eeg_comps_flat_concat_dict is not None
                # merged_bad_epoch_intervals_df: pd.DataFrame = eeg_comps_flat_concat_dict.get('merged_bad_epoch_intervals_df', None)

                merged_bad_epoch_intervals_df: pd.DataFrame = eeg_ds.merged_bad_epoch_intervals_df.copy()
                # assert merged_bad_epoch_intervals_df is not None

                if merged_bad_epoch_intervals_df is None:
                    print(f'WARNING: {merged_bad_epoch_intervals_df} is None!')
                    return None

                #TODO 2026-04-03 08:57: - [ ] needs timeline `timeline`
                _common_kwargs = dict(time_offset=0)

                if include_overlays_on_timeline_tracks:
                    new_regions = apply_bad_epochs_overlays_to_timeline(timeline, merged_bad_epoch_intervals_df, add_interval_track=include_dedicated_interval_track, **_common_kwargs)


                if include_dedicated_interval_track:
                    ensure_bad_epochs_interval_track(timeline, merged_bad_epoch_intervals_df, **_common_kwargs)

                return merged_bad_epoch_intervals_df


            ## reset
            self.merged_bad_epoch_intervals_df = None
            self.merged_bad_epoch_intervals_plot_callback_fn = None
            
            eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(self, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict) ## sets `eeg_ds.merged_bad_epoch_intervals_df`, doesn't change `eeg_comps_flat_concat_dict`

            # merged_bad_epoch_intervals_plot_callback_fn = lambda eeg_ds, timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=eeg_ds, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)

            ## this version captures `self`
            merged_bad_epoch_intervals_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=self, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)

            # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_plot_callback_fn'] = merged_bad_epoch_intervals_plot_callback_fn
            # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']
            self.merged_bad_epoch_intervals_plot_callback_fn = merged_bad_epoch_intervals_plot_callback_fn

            # ## USAGE:
            #     eeg_ds.merged_bad_epoch_intervals_plot_callback_fn(timeline=timeline, include_overlays_on_timeline_tracks=True)



        # for a_specific_computed_goal_name, a_specific_computed_value_list in eeg_comps_flat_concat_dict.items():
        #     for a_specific_computed_value in (a_specific_computed_value_list or []):
        #         if a_specific_computed_value is not None:
        #             ## do the post-compute stuff
        #             if a_specific_computed_goal_name == 'bad_epochs': # in eeg_comps_flat_concat_dict:
        #                 ## tries to provide keys: eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']

        #                 def _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict) -> pd.DataFrame:
        #                     """ computes the bad epoch times for Dose/MOTION tracks and optinally adds them to the timeline to preview 

        #                         eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

        #                     """
        #                     ## INPUTS: eeg_ds, eeg_comps_flat_concat_dict
        #                     ## UPDATES: eeg_comps_flat_concat_dict
        #                     # bad_epochs_intervals_df_t_col_names: str = ['start_t', 'end_t']
        #                     bad_epochs_intervals_df_t_col_names: str = ['t_start', 't_end']
        #                     bad_epochs_intervals_df_non_descript_rel_t_col_names = [f'{a_t_col}_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

        #                     bad_epochs_intervals_df_sess_rel_t_col_names = [f'{a_t_col}_sess_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]
        #                     bad_epochs_intervals_df_timeline_rel_t_col_names = [f'{a_t_col}_timeline_rel' for a_t_col in bad_epochs_intervals_df_t_col_names]

        #                     active_col_names = ['t_start', 't_start_dt', 't_end', 't_end_dt', 't_duration']
        #                     rename_fn = lambda df: df.rename(columns=dict(zip(['start_t', 'end_t', 'start_t_rel', 'end_t_rel', 'start_t_dt', 'end_t_dt', 'duration'], ['t_start', 't_end', 't_start_rel', 't_end_rel', 't_start_dt', 't_end_dt', 't_duration'])), inplace=False)

        #                     ds_overview_intervals_df: pd.DataFrame = eeg_ds.get_overview_intervals()[active_col_names].sort_values(active_col_names).reset_index(drop=True)

        #                     for idx, a_bad_epochs_result_dict in enumerate(eeg_comps_flat_concat_dict['bad_epochs']):
        #                         active_interval_row = ds_overview_intervals_df.iloc[idx].to_dict()
        #                         active_interval_t_start: float = active_interval_row['t_start']
        #                         a_bad_epochs_df = a_bad_epochs_result_dict.get('bad_epoch_intervals_df', None)
        #                         # a_bad_epochs_df = a_bad_epochs_result_dict.pop('bad_epoch_intervals_df', None)
        #                         if a_bad_epochs_df is not None:
        #                             a_bad_epochs_df = rename_fn(a_bad_epochs_df)
        #                             print(f'idx: {idx}, active_interval_t_start: {active_interval_t_start}, {active_interval_row}:')
        #                             for a_t_col in bad_epochs_intervals_df_t_col_names:
        #                                 a_bad_epochs_df[a_t_col] = a_bad_epochs_df[f'{a_t_col}_rel'] + active_interval_t_start ## these are relative to each individual session/recording, not the timeline start or the earliest recording
                                        
        #                             a_bad_epochs_df['eeg_raw_idx'] = idx
        #                             a_bad_epochs_result_dict['bad_epoch_intervals_df'] = a_bad_epochs_df ## re-apply

        #                     # [v.get('bad_epoch_intervals_df', None) for idx, v in enumerate(eeg_comps_flat_concat_dict['bad_epochs'])]
        #                     merged_bad_epoch_intervals_df: pd.DataFrame = pd.concat([v.get('bad_epoch_intervals_df', None) for v in eeg_comps_flat_concat_dict['bad_epochs']])
        #                     # merged_bad_epoch_intervals_df
        #                     merged_bad_epoch_intervals_df = rename_fn(merged_bad_epoch_intervals_df)
        #                     earliest_interval_t_start: float = np.nanmin(ds_overview_intervals_df['t_start'].to_numpy())
        #                     merged_bad_epoch_intervals_df[bad_epochs_intervals_df_timeline_rel_t_col_names] = merged_bad_epoch_intervals_df[bad_epochs_intervals_df_t_col_names] - earliest_interval_t_start ## timeline start relative
        #                     merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df.rename(columns=dict(zip(bad_epochs_intervals_df_non_descript_rel_t_col_names, bad_epochs_intervals_df_sess_rel_t_col_names)), inplace=False) ## indicate that the non-descript '*_rel' columns are actually '*_sess_rel' columns
        #                     merged_bad_epoch_intervals_df

        #                     # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df'] = merged_bad_epoch_intervals_df
        #                     eeg_ds.merged_bad_epoch_intervals_df = merged_bad_epoch_intervals_df

        #                     ## OUTPUTS: merged_bad_epoch_intervals_df
        #                     return eeg_comps_flat_concat_dict
        #                 ## END def _subfn_post_compute_build_merged_bad_epochs(e....
                        
        #                 def _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds, eeg_comps_flat_concat_dict, timeline, include_overlays_on_timeline_tracks: bool=True, include_dedicated_interval_track: bool=False) -> pd.DataFrame:
        #                     """ plots the bad epochs on the Dose/MOTION views and optionally as a separate track

        #                         a_plot_callback_fn = lambda timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(timeline=timeline, eeg_ds=eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
        #                     """
        #                     from phopymnehelper.analysis.computations.specific.bad_epochs import ensure_bad_epochs_interval_track, apply_bad_epochs_overlays_to_timeline

        #                     assert eeg_comps_flat_concat_dict is not None
        #                     merged_bad_epoch_intervals_df: pd.DataFrame = eeg_comps_flat_concat_dict.get('merged_bad_epoch_intervals_df', None)

        #                     if merged_bad_epoch_intervals_df is None:
        #                         print(f'WARNING: {merged_bad_epoch_intervals_df} is None!')
        #                         return None

        #                     #TODO 2026-04-03 08:57: - [ ] needs timeline `timeline`
        #                     _common_kwargs = dict(time_offset=0)

        #                     if include_overlays_on_timeline_tracks:
        #                         new_regions = apply_bad_epochs_overlays_to_timeline(timeline, merged_bad_epoch_intervals_df, add_interval_track=include_dedicated_interval_track, **_common_kwargs)


        #                     if include_dedicated_interval_track:
        #                         ensure_bad_epochs_interval_track(timeline, merged_bad_epoch_intervals_df, **_common_kwargs)

        #                     return merged_bad_epoch_intervals_df


        #                 ## reset
        #                 self.merged_bad_epoch_intervals_df = None
        #                 self.merged_bad_epoch_intervals_plot_callback_fn = None
                        
        #                 eeg_comps_flat_concat_dict = _subfn_post_compute_build_merged_bad_epochs(self, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict)

        #                 merged_bad_epoch_intervals_plot_callback_fn = lambda eeg_ds, timeline: _subfn_post_compute_post_build_display_merged_bad_epochs(eeg_ds=eeg_ds, eeg_comps_flat_concat_dict=eeg_comps_flat_concat_dict, timeline=timeline, include_overlays_on_timeline_tracks=True, include_dedicated_interval_track=False)
        #                 # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_plot_callback_fn'] = merged_bad_epoch_intervals_plot_callback_fn
        #                 # eeg_comps_flat_concat_dict['merged_bad_epoch_intervals_df']
        #                 self.merged_bad_epoch_intervals_plot_callback_fn = merged_bad_epoch_intervals_plot_callback_fn

        #                 # ## USAGE:
        #                 #     eeg_ds.merged_bad_epoch_intervals_plot_callback_fn(timeline=timeline, include_overlays_on_timeline_tracks=True)




        self.sigSourceComputeFinished.emit(was_success)


    def get_computed_results_for_sess(self, sess_idx: int) -> Dict[types.DoseComputationId, Dict[str, Any]]:
        """ gets the results filtered for only the single session

        Usage:

            desired_sess_idx: int = (eeg_ds.num_sessions - 1) ## last session
            filtered_computed_result: Dict[types.DoseComputationId, Dict[str, Any]] = eeg_ds.get_computed_results_for_sess(sess_idx=desired_sess_idx)
            filtered_computed_result

        """
        assert (sess_idx < self.num_sessions), f"sess_idx: {sess_idx} but max allowed index is (self.num_sessions - 1): {(self.num_sessions - 1)}"
        # computed_result: Dict[types.DoseComputationId, List[Dict[str, Any]]] = self.computed_result # Each list has one entry per eeg_sess
        filtered_computed_result: Dict[types.DoseComputationId, Dict[str, Any]] = {k:v[sess_idx] for k, v in self.computed_result.items()} ## filtered for only the single session
        return filtered_computed_result


    def add_spectrogram_tracks_for_channel_groups(self, spectrogram_channel_groups: Optional[List[SpectrogramChannelGroupConfig]], timeline: "SimpleTimelineWidget", timeline_builder: "TimelineBuilder", *, update_time_range: bool = False, skip_existing_names: bool = True) -> List["DoseSpectrogramTrackDatasource"]:
        """Compute interval-aligned spectrograms from raws, create one ``DoseSpectrogramTrackDatasource`` child per channel group (shared STFT, differing ``group_config``), and append tracks via ``timeline_builder.update_timeline``.

        When ``spectrogram_channel_groups`` is None or empty, adds a single spectrogram track (all channels averaged). Names use prefix ``Dose_Spectrogram_<suffix>`` so dock grouping matches ``stream_to_datasources``.
        """
        if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
            if self.parent() is not None and getattr(self.parent(), "raw_datasets_dict", None) is not None:
                self.raw_datasets_dict = self.parent().raw_datasets_dict
        if len(self._flatten_raw_lists_from_dict(self.raw_datasets_dict)) < 1:
            logger.warning("add_spectrogram_tracks_for_channel_groups: no raws in raw_datasets_dict for %s; skipping.", self.custom_datasource_name)
            return []
        spec_results = compute_multiraw_spectrogram_results(self.intervals_df, self.raw_datasets_dict)
        name_prefix = _eeg_parent_spectrogram_track_name_prefix(self.custom_datasource_name)
        _effective_groups: Optional[List[SpectrogramChannelGroupConfig]] = spectrogram_channel_groups if (spectrogram_channel_groups is not None and len(spectrogram_channel_groups) > 0) else None
        specs: List[Tuple[str, Optional[SpectrogramChannelGroupConfig], Optional[List[SpectrogramChannelGroupConfig]]]] = []
        if _effective_groups is None:
            specs.append((name_prefix, None, None))
        else:
            for group_cfg in _effective_groups:
                specs.append((f"{name_prefix}_{group_cfg.name}", SpectrogramChannelGroupConfig(name=group_cfg.name, channels=list(group_cfg.channels)), _effective_groups))
        created: List[Any] = []
        for track_name, gcfg, presets in specs:
            if skip_existing_names and track_name in timeline.track_datasources:
                logger.debug("add_spectrogram_tracks_for_channel_groups: skip existing track %r", track_name)
                continue
            child: DoseSpectrogramTrackDatasource = DoseSpectrogramTrackDatasource(intervals_df=self.intervals_df.copy(), spectrogram_result=None, spectrogram_results=spec_results, custom_datasource_name=track_name, group_config=gcfg, channel_group_presets=presets, lab_obj_dict=self.lab_obj_dict, raw_datasets_dict=self.raw_datasets_dict, parent=self)
            created.append(child)
        if getattr(self, "_spectrogram_child_datasources", None) is None:
            self._spectrogram_child_datasources = []
        self._spectrogram_child_datasources.extend(created)
        if len(created) > 0:
            timeline_builder.update_timeline(timeline, [*created], update_time_range=update_time_range)
        return created



__all__ = ['DosePlotDetailRenderer', 'DoseTrackDatasource'] # , 'DoseTrackDatasource'

