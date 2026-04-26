from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from qtpy import QtCore
from typing import Dict, List, Mapping, Tuple, Optional, Callable, Union, Any, Sequence, cast
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource, ComputableDatasourceMixin

from pypho_timeline.utils.logging_util import get_rendering_logger
logger = get_rendering_logger(__name__)

from dose_analysis_python.DoseCurveCalculation.pysb_pkpd_da_ne_monoamine import PySbPKPD_DA_NE_DoseCurveModel
from dose_analysis_python.FileImportExport.DoseImporter import DoseNoteFragmentParser
from dose_analysis_python.service.lsl_monitor import parse_lsl_dose_sample
from phopylslhelper.datetime_helpers import to_display_timezone, unix_timestamp_to_datetime, float_to_datetime
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dose_analysis_python.Helpers.quantization import Quanta, ComputationTimeBlock

import pypho_timeline.EXTERNAL.pyqtgraph as pg
from pypho_timeline.rendering.helpers import ChannelNormalizationMode
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer


# ==================================================================================================================================================================================================================================================================================== #
# DoseCurvePlotDetailRenderer                                                                                                                                                                                                                                                           #
# ==================================================================================================================================================================================================================================================================================== #
class DoseCurvePlotDetailRenderer(DataframePlotDetailRenderer):
    """DataframePlotDetailRenderer subclass that adds a top-right PyQtGraph legend for dose curve channels.

    The legend is created (or reused if already present) via ``PlotItem.addLegend`` before handing off
    to the parent ``render_detail``.  Because the parent already constructs every ``PlotDataItem`` with
    ``name=channel_name``, and PyQtGraph's ``PlotItem.addItem`` auto-registers named items in an
    existing legend, no extra bookkeeping is required.

    Usage:
        renderer = DoseCurvePlotDetailRenderer(channel_names=['AMPH_gut', 'DA_str'], pen_width=1.5)
    """

    def render_detail(self, plot_item: pg.PlotItem, interval, detail_data) -> list:
        if detail_data is None or (hasattr(detail_data, '__len__') and len(detail_data) == 0):
            return []
        plot_item.addLegend(offset=(-10, 10), labelTextColor='w', brush=(30, 30, 30, 180), labelTextSize='7pt', horSpacing=10, verSpacing=-2)
        return super().render_detail(plot_item, interval, detail_data)


# ==================================================================================================================================================================================================================================================================================== #
# DoseTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #
class DoseTrackDatasource(ComputableDatasourceMixin, IntervalProvidingTrackDatasource):
    """TrackDatasource for text-log-derived dose curves backed by interval/detail DataFrames.

    Extends IntervalProvidingTrackDatasource for dose-curve detail rendering and async detail loading.

    Parsing uses the same cascade as the live LSL dose monitor (``parse_lsl_dose_sample``), so
    all known message formats are handled correctly regardless of which log stream they come from:
    JSON markers, EventBoard ``DOSE_*|...|...`` lines, transcript ``"N plus"`` tokens, note
    fragments, and bare numeric tokens.

    Usage — single source track::

        from pypho_timeline.rendering.datasources.specific.dose import DoseTrackDatasource

        dose_curve_ds = DoseTrackDatasource.init_from_timeline_text_log_tracks(timeline=timeline)
        # or from an EventBoard stream:
        dose_curve_ds = DoseTrackDatasource.init_from_timeline_text_log_tracks(timeline=timeline, source_track_name='LOG_EventBoard')

    Usage — merge multiple source tracks::

        dose_curve_ds = DoseTrackDatasource.init_from_timeline_text_log_tracks(
            timeline=timeline, source_track_name=['LOG_TextLogger', 'LOG_EventBoard'])

    """
    sigSourceComputeStarted = QtCore.Signal()
    sigSourceComputeFinished = QtCore.Signal(bool)
    DEFAULT_CURVE_CHANNEL_NAMES = ['AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf', 'DA_str', 'NE_pfc', 'DA_pfc']
    DEFAULT_NORMALIZATION_MODE_DICT = {('AMPH_gut', 'AMPH_blood', 'AMPH_brain', 'AMPH_ecf'): ChannelNormalizationMode.GROUPMINMAXRANGE, ('DA_str', 'DA_pfc'): ChannelNormalizationMode.GROUPMINMAXRANGE, ('NE_pfc',): ChannelNormalizationMode.GROUPMINMAXRANGE}


    def __init__(self, intervals_df: pd.DataFrame, recordSeries_df: pd.DataFrame, complete_curve_df: pd.DataFrame, custom_datasource_name: Optional[str]=None, max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True, fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None, parent: Optional[QtCore.QObject] = None, plot_pen_colors: Optional[List[str]] = None, plot_pen_width: Optional[float] = None):
        """Initialize a dataframe-backed datasource for precomputed dose curves."""
        if custom_datasource_name is None:
            custom_datasource_name = "DoseTrack"
        if channel_names is None:
            channel_names = self._get_curve_channel_names(complete_curve_df)
        curve_df = self._build_curve_detail_df(complete_curve_df=complete_curve_df, curve_channel_names=channel_names)
        super().__init__(intervals_df, detailed_df=curve_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, parent=parent)
        self.recordSeries_df = recordSeries_df.copy()
        self.complete_curve_df = complete_curve_df.copy()

        if (normalization_reference_df is None) and (self.detailed_df is not None):
            normalization_reference_df = self.detailed_df

        self.fallback_normalization_mode = fallback_normalization_mode
        self.normalization_mode_dict = normalization_mode_dict if normalization_mode_dict is not None else self.DEFAULT_NORMALIZATION_MODE_DICT
        self.arbitrary_bounds = arbitrary_bounds
        self.normalize = normalize
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
    def _get_curve_channel_names(cls, complete_curve_df: pd.DataFrame) -> List[str]:
        return [col for col in cls.DEFAULT_CURVE_CHANNEL_NAMES if col in complete_curve_df.columns]


    @classmethod
    def _build_curve_detail_df(cls, complete_curve_df: pd.DataFrame, curve_channel_names: Optional[List[str]]=None) -> pd.DataFrame:
        if curve_channel_names is None:
            curve_channel_names = cls._get_curve_channel_names(complete_curve_df)
        if 't' not in complete_curve_df.columns:
            raise ValueError("complete_curve_df must include a 't' column")
        if len(curve_channel_names) == 0:
            raise ValueError("complete_curve_df does not include any known dose curve channels")
        return complete_curve_df[['t'] + curve_channel_names].copy()


    @classmethod
    def _text_log_rows_to_record_series_df(cls, detailed_txt_log_df: pd.DataFrame, default_medication: str = 'AMPH') -> pd.DataFrame:
        """Parse all message rows using the shared LSL dose-sample parsing cascade.

        Handles all known log formats in order of specificity:
          - JSON dose markers  (``{"dose_mg": ..., ...}``)
          - EventBoard markers (``DOSE_AMPH_...|Dose 10+|2024-...``)
          - Transcript tokens  (``"10 plus"``)
          - Note fragments     (lines containing ``-``, multi-event)
          - Bare numeric tokens (``"10+"`` / ``"10"``)

        One log row may expand to *multiple* ``recordSeries_df`` rows when the
        message encodes several events (JSON array, note fragment).

        Parameters
        ----------
        detailed_txt_log_df:
            DataFrame with at minimum a ``msg`` column (str) and a ``dt`` column
            (wall-clock datetimes, already set as the index or as a regular column).
        default_medication:
            Medication name used when the message does not specify one.

        Returns
        -------
        pd.DataFrame
            Index ``recordDoseDate`` (tz-aware US/Eastern ``DatetimeIndex``),
            columns ``recordDoseValue`` (float), ``modifier`` (str),
            ``medication`` (str).  Empty DataFrame with those columns when
            nothing parses as a dose event.
        """
        if 'msg' not in detailed_txt_log_df.columns:
            raise ValueError("detailed_txt_log_df must include a 'msg' column")
        if 'dt' not in detailed_txt_log_df.columns:
            raise ValueError("detailed_txt_log_df must include a 'dt' column (wall-clock datetime)")
        tz = ZoneInfo("US/Eastern")
        records: List[Dict[str, Any]] = []
        for _, row in detailed_txt_log_df.iterrows():
            dt_val = row['dt']
            sample_time: datetime = dt_val.to_pydatetime() if isinstance(dt_val, pd.Timestamp) else dt_val
            if sample_time.tzinfo is None or sample_time.utcoffset() is None:
                sample_time = sample_time.replace(tzinfo=tz)
            else:
                sample_time = sample_time.astimezone(tz)
            events = parse_lsl_dose_sample(sample=row['msg'], sample_time=sample_time, default_medication=default_medication)
            for evt in events:
                records.append({'recordDoseDate': pd.Timestamp(evt.event_time.astimezone(tz)), 'recordDoseValue': float(evt.dose_mg), 'modifier': str(evt.modifier), 'medication': str(evt.medication)})
        if not records:
            return pd.DataFrame(columns=['recordDoseValue', 'modifier', 'medication']).rename_axis('recordDoseDate')
        recordSeries_df: pd.DataFrame = pd.DataFrame(records).set_index('recordDoseDate', drop=True)
        recordSeries_idx = cast(Any, pd.DatetimeIndex(recordSeries_df.index))
        if recordSeries_idx.tz is None:
            recordSeries_df.index = recordSeries_idx.tz_localize("US/Eastern")
        else:
            recordSeries_df.index = recordSeries_idx.tz_convert("US/Eastern")
        return recordSeries_df


    @classmethod
    def init_from_timeline_text_log_tracks(cls, timeline, track_name: str='DOSE_CURVES_Computed', source_track_name: Union[str, Sequence[str]]=['LOG_TextLogger', 'LOG_EventBoard'], backend: str='scipy', max_events: int=120, follow_h_after_last: float=12.0, default_medication: str='AMPH') -> "DoseTrackDatasource":
        """Build dose curves from one or more timeline text-log tracks.

        Parsing matches the live LSL dose monitoring pipeline (``parse_lsl_dose_sample``),
        so all known message formats are recognised:
          - JSON dose markers
          - EventBoard ``DOSE_*|...|...`` markers (e.g. from ``LOG_EventBoard``)
          - Transcript ``"N plus"`` tokens (e.g. from ``LOG_TextLogger``)
          - Note fragments (lines containing ``-``)
          - Bare numeric tokens

        Parameters
        ----------
        source_track_name:
            A single track name (str) or a sequence of track names.  When multiple
            names are given the rows from all present tracks are concatenated and
            sorted by wall-clock time before parsing.  Tracks that do not exist in
            the timeline are skipped with a warning; a ``ValueError`` is raised only
            if *none* of the requested tracks exist.

            Note: the same dose event logged to both ``LOG_TextLogger`` and
            ``LOG_EventBoard`` will produce two ``recordSeries_df`` rows — downstream
            PK/PD computation is tolerant of this but you can avoid it by passing
            only one source.
        """
        track_names: List[str] = [source_track_name] if isinstance(source_track_name, str) else list(source_track_name)
        available = set(timeline.track_datasources.keys())
        frames: List[pd.DataFrame] = []
        for name in track_names:
            if name not in available:
                logger.warning("init_from_timeline_text_log_tracks: track %r not found in timeline (available: %s); skipping.", name, sorted(available))
                continue
            _, _, txt_log_ds = timeline.get_track_tuple(name)
            frame: pd.DataFrame = txt_log_ds.detailed_df.copy().reset_index(drop=True)
            if 't' not in frame.columns:
                raise ValueError(f"Text log track {name!r} must include a 't' column")
            if 'dt' not in frame.columns:
                frame['dt'] = float_to_datetime(frame['t'].to_numpy(), reference_datetime=timeline.reference_datetime)
            frames.append(frame)
        if not frames:
            raise ValueError(f"None of the requested source tracks exist in the timeline. Requested: {track_names!r}. Available: {sorted(available)!r}")
        detailed_txt_log_df: pd.DataFrame = pd.concat(frames, ignore_index=True).sort_values('dt').reset_index(drop=True)
        detailed_txt_log_df = detailed_txt_log_df.set_index('dt', drop=False, inplace=False)
        recordSeries_df = cls._text_log_rows_to_record_series_df(detailed_txt_log_df, default_medication=default_medication)
        if len(recordSeries_df) == 0:
            raise ValueError(f"No dose events found in text log track(s) {track_names!r}")
        start_date: datetime = timeline.total_data_start_time
        end_date: Optional[datetime] = timeline.total_data_end_time
        compute_result = cast(Any, ComputationTimeBlock.init_from_start_end_date(parsed_record_df=recordSeries_df, start_date=start_date, end_date=end_date, backend=backend, max_events=max_events, follow_h_after_last=follow_h_after_last))
        _, complete_curve_df = compute_result
        complete_curve_df = cast(pd.DataFrame, complete_curve_df)
        curve_channel_names = cls._get_curve_channel_names(complete_curve_df)
        curve_df = cls._build_curve_detail_df(complete_curve_df=complete_curve_df, curve_channel_names=curve_channel_names)
        interval_start = pd.Timestamp(curve_df['t'].min())
        interval_end = pd.Timestamp(curve_df['t'].max())
        interval_duration_seconds = (interval_end - interval_start).total_seconds()
        intervals_df = pd.DataFrame({'t_start': [interval_start], 't_duration': [interval_duration_seconds]})
        return cls(intervals_df=intervals_df, recordSeries_df=recordSeries_df, complete_curve_df=complete_curve_df, custom_datasource_name=track_name, channel_names=curve_channel_names, enable_downsampling=False, plot_pen_width=1.5)


    @classmethod
    def build_dose_curve_track(cls, timeline: "SimpleTimelineWidget", timeline_builder: "TimelineBuilder", track_name: str='DOSE_CURVES_Computed', source_track_name: Union[str, Sequence[str]]=['LOG_TextLogger', 'LOG_EventBoard'], backend: str='scipy', max_events: int=120, follow_h_after_last: float=12.0, default_medication: str='AMPH', *, update_time_range: bool=False, skip_existing_names: bool=True) -> Optional["DoseTrackDatasource"]:
        """Build dose curves from one or more timeline text-log tracks and add as a new track.

        Builds a ``DoseTrackDatasource`` via ``init_from_timeline_text_log_tracks``, then adds
        it to the timeline using ``timeline_builder.update_timeline``.  If the track already
        exists and ``skip_existing_names`` is True, the existing datasource is returned without
        rebuilding.

        ``source_track_name`` accepts either a single track name or a sequence of names — see
        ``init_from_timeline_text_log_tracks`` for details on multi-track merging.

        Usage:
            dose_curve_ds = DoseTrackDatasource.build_dose_curve_track(timeline=timeline, timeline_builder=builder, source_track_name='LOG_EventBoard')
            dose_curve_ds = DoseTrackDatasource.build_dose_curve_track(timeline=timeline, timeline_builder=builder, source_track_name=['LOG_TextLogger', 'LOG_EventBoard'])
        """
        if skip_existing_names and (track_name in timeline.track_datasources):
            logger.debug("build_dose_curve_track: skip existing track %r", track_name)
            return cast(Optional["DoseTrackDatasource"], timeline.track_datasources.get(track_name))
        dose_curve_ds = cls.init_from_timeline_text_log_tracks(timeline=timeline, track_name=track_name, source_track_name=source_track_name, backend=backend, max_events=max_events, follow_h_after_last=follow_h_after_last, default_medication=default_medication)
        timeline_builder.update_timeline(timeline, [dose_curve_ds], update_time_range=update_time_range)
        return dose_curve_ds


    @property
    def num_sessions(self) -> int:
        """The num_sessions property."""
        return len(self.intervals_df)


    def get_detail_renderer(self):
        """Get detail renderer for computed dose curve data."""
        _extra_kw: Dict[str, Any] = {'channel_names': self.channel_names} if self.channel_names is not None else {}
        if self.plot_pen_colors is not None:
            _extra_kw['pen_colors'] = self.plot_pen_colors
        _pen_width = 1.5 if self.plot_pen_width is None else self.plot_pen_width
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
        return DoseCurvePlotDetailRenderer(pen_width=cast(Any, _pen_width), fallback_normalization_mode=self.fallback_normalization_mode, normalization_mode_dict=self.normalization_mode_dict, arbitrary_bounds=self.arbitrary_bounds, normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df, **_extra_kw)



    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get cache key for interval (single-row DataFrame or Series)."""
        return super().get_detail_cache_key(interval)


    '''
    Unfinished copied methods below are intentionally disabled while DoseTrackDatasource only supports
    the init_from_timeline_text_log_tracks path.

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



    '''


__all__ = ['DoseTrackDatasource']

