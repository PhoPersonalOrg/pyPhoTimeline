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


def _coerce_time_value_to_unix(value: Any) -> float:
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        if len(value) == 0:
            return float("nan")
        value = value[0]
    if pd.isna(value):
        return float("nan")
    if isinstance(value, (datetime, pd.Timestamp)):
        return float(datetime_to_unix_timestamp(value))
    if isinstance(value, (pd.Timedelta, np.timedelta64)):
        return float(pd.Timedelta(value).total_seconds())
    return float(value)


def _coerce_time_series_to_unix(values: pd.Series) -> np.ndarray:
    if pd.api.types.is_datetime64_any_dtype(values):
        coerced = pd.to_datetime(values, utc=True, errors="coerce")
        return (coerced.astype("int64") / 1e9).to_numpy(dtype=float, copy=False)
    return pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, copy=False)


def _interval_row_to_unix_bounds(interval_row: pd.Series) -> Tuple[float, float]:
    t_start = _coerce_time_value_to_unix(interval_row["t_start"])
    if "t_end" in interval_row and pd.notna(interval_row["t_end"]):
        return t_start, _coerce_time_value_to_unix(interval_row["t_end"])
    t_duration = interval_row["t_duration"] if "t_duration" in interval_row.index else 0.0
    if isinstance(t_duration, (pd.Timedelta, np.timedelta64)):
        t_duration = pd.Timedelta(t_duration).total_seconds()
    return t_start, t_start + float(t_duration)


def aligned_chronological_raws_for_intervals(intervals_df: pd.DataFrame, raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> Tuple[List[Any], int]:
    raws = RawProvidingTrackDatasource.get_sorted_and_extracted_raws(raw_datasets_dict)
    raws_list: List[Any] = list(raws) if isinstance(raws, list) else list(raws.values()) if isinstance(raws, dict) else []
    n_iv = len(intervals_df)
    if n_iv == 0 or not raws_list:
        return [], 0
    n = min(len(raws_list), n_iv)
    if len(raws_list) != n_iv:
        logger.warning("EEG multiraw alignment: raw count (%s) != interval count (%s); using %s chronological raws aligned to interval rows; excess raws or intervals have no matching raw-backed artifact.", len(raws_list), n_iv, n)
    return raws_list, n


def compute_multiraw_spectrogram_results(intervals_df: pd.DataFrame, raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> List[Optional[Dict[str, Any]]]:
    from phopymnehelper.analysis.computations.eeg_registry import run_eeg_computations_graph, session_fingerprint_for_raw_or_path
    raws, n = aligned_chronological_raws_for_intervals(intervals_df=intervals_df, raw_datasets_dict=raw_datasets_dict)
    if n == 0:
        return []
    n_iv = len(intervals_df)
    out: List[Optional[Dict[str, Any]]] = [None] * n_iv
    for i in range(n):
        raw = raws[i]
        eeg_comps_result = run_eeg_computations_graph(raw, session=session_fingerprint_for_raw_or_path(raw), goals=("spectogram",))
        out[i] = eeg_comps_result.get("spectogram")
    return out


@dataclass
class SpectrogramChannelGroupConfig:
    """Defines a named group of EEG channels to average for one spectrogram track."""
    name: str
    channels: List[str]


def _eeg_parent_spectrogram_track_name_prefix(parent_custom_name: Optional[str]) -> str:
    """Build ``EEG_Spectrogram_<suffix>`` prefix from an EEG track name (matches stream_to_datasources naming)."""
    n = parent_custom_name or "EEG"
    suffix = n[4:] if n.startswith("EEG_") else n
    return f"EEG_Spectrogram_{suffix}"


def _first_sfreq_from_raw_datasets_dict(raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> Optional[float]:
    """First positive ``sfreq`` from MNE ``Raw`` objects in ``raw_datasets_dict`` (GFP band-pass needs acquisition rate)."""
    if not raw_datasets_dict:
        return None
    for _key, lst in raw_datasets_dict.items():
        if not lst:
            continue
        for raw in lst:
            if raw is None:
                continue
            try:
                info = getattr(raw, "info", None)
                if info is None:
                    continue
                sf = float(info.get("sfreq", 0.0) or 0.0)
                if sf > 0.0:
                    return sf
            except Exception:
                continue
    return None


EMOTIV_EPOC_X_SPECTROGRAM_GROUPS: List[SpectrogramChannelGroupConfig] = [
    # SpectrogramChannelGroupConfig(name='Frontal-L', channels=['AF3', 'F7', 'FC5', 'F3']),
    # SpectrogramChannelGroupConfig(name='Frontal-R', channels=['AF4', 'F8', 'FC6', 'F4']),
    # SpectrogramChannelGroupConfig(name='Posterior-L', channels=['T7', 'P7', 'O1']),
    # SpectrogramChannelGroupConfig(name='Posterior-R', channels=['T8', 'P8', 'O2']),
    SpectrogramChannelGroupConfig(name='Frontal', channels=['AF3', 'F7', 'FC5', 'F3', 'AF4', 'F8', 'FC6', 'F4']),
    SpectrogramChannelGroupConfig(name='Posterior', channels=['T7', 'P7', 'O1', 'T8', 'P8', 'O2']),
    SpectrogramChannelGroupConfig(name='All', channels=['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']),
]

# ==================================================================================================================================================================================================================================================================================== #
# EEGPlotDetailRenderer - Renders eeg data as line plots.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #
import pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode, ChannelNormalizationModeNormalizingMixin
try:
    from pyphocorehelpers.function_helpers import function_attributes
except ImportError:
    function_attributes = lambda **kw: lambda f: f


## NOTE: Currently inherits directly from DetailRenderer protocol. GenericPlotDetailRenderer is designed
## to wrap functions rather than for traditional inheritance. MotionPlotDetailRenderer follows the same pattern.
class EEGPlotDetailRenderer(ChannelNormalizationModeNormalizingMixin, DetailRenderer):
    """Detail renderer for eeg tracks that displays eeg channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns
    (e.g., ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']).

    Usage:
        from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer, EEGTrackDatasource, SpectrogramChannelGroupConfig

    """
    
    def __init__(self, pen_width=1, channel_names=['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'], pen_colors=None,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None,
                 **kwargs,
                 ):
        """Initialize the eeg plot renderer.
        
        Args:
            pen_color: Default color for channels (used if channel_names is None, default: 'cyan')
            pen_width: Width of the plot lines (default: 2)
            channel_names: List of channel names to plot (default: ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'])
            pen_colors: Optional list of colors for each channel (default: None, auto-generated)
        """
        ChannelNormalizationModeNormalizingMixin.__init__(self, channel_names=channel_names, fallback_normalization_mode=fallback_normalization_mode, normalization_mode_dict=normalization_mode_dict, arbitrary_bounds=arbitrary_bounds,
                                                         normalize=normalize, normalize_over_full_data=normalize_over_full_data, normalization_reference_df=normalization_reference_df)
        DetailRenderer.__init__(self, **kwargs)

        self.pen_colors = pen_colors
        self.pen_width = pen_width
        self.channel_names = channel_names

        # Generate distinct colors for each channel
        if (channel_names is not None) and (pen_colors is None):
            # Predefined palette of distinct colors
            # Generate enough distinct colors for all EEG channels using matplotlib's colormap
            import matplotlib.pyplot as plt
            import matplotlib
            # We'll use 'tab20' which has 20 distinct colors, enough for 14 channels
            num_channels = len(channel_names)
            # Use a rainbow colormap suitable for black/dark backgrounds. 
            # 'nipy_spectral' and 'turbo' are perceptually uniform and good for this.
            cmap = plt.get_cmap('nipy_spectral')
            color_palette = [matplotlib.colors.to_hex(cmap(i / max(num_channels-1, 1))) for i in range(num_channels)]
            # Cycle through palette if more channels than colors
            self.pen_colors = [color_palette[i % len(color_palette)] for i in range(len(channel_names))]
        else:
            self.pen_colors = None



    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render eeg data as line plots for each channel.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)

        Usage:
            a_track_name: str = 'MOTION_Epoc X EEG'
            a_renderer = timeline.track_renderers[a_track_name]
            a_detail_renderer = a_renderer.detail_renderer # EEGPlotDetailRenderer 
            a_ds = timeline.track_datasources[a_track_name]
            interval = a_ds.get_overview_intervals()

            dDisplayItem = timeline.ui.dynamic_docked_widget_container.find_display_dock(identifier=a_track_name) # Dock
            a_widget = timeline.ui.matplotlib_view_widgets[a_track_name] # PyqtgraphTimeSynchronizedWidget 
            a_root_graphics_layout_widget = a_widget.getRootGraphicsLayoutWidget()
            a_plot_item = a_widget.getRootPlotItem()

            graphics_objects = a_detail_renderer.render_detail(plot_item=a_plot_item, interval=None, detail_data=a_ds.detailed_df) # List[PlotDataItem]

        """
        logger.debug(f"EEGPlotDetailRenderer[].render_detail(plot_item: {plot_item},\n\tinterval='{interval}',\n\t detail_data={detail_data}) - starting")
    
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"EEGPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
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

        channel_graphics_items, channel_label_items = self.add_channel_renderables_if_needed(plot_item=plot_item)
        graphics_objects = list(channel_graphics_items)

        # Filter channels based on visibility if channel_visibility is set
        if hasattr(self, 'channel_visibility') and self.channel_visibility:
            found_channel_names = [ch for ch in found_channel_names if self.channel_visibility.get(ch, True)]

        # Normalize channel columns using shared helper
        normalized_channel_df, (y_min, y_max) = self.compute_normalized_channels(detail_df=df_sorted, channel_names=found_channel_names)

        # Extract t_values aligned with normalized_channel_df's index to ensure shape matches
        # normalized_channel_df may have fewer rows due to index intersection during normalization
        t_col_aligned = df_sorted.loc[normalized_channel_df.index, 't']
        t_values = t_col_aligned.to_numpy(dtype=float, copy=False)

        # Keep detailed EEG x-values in the owning interval bounds; if there is no overlap,
        # fallback to evenly rebasing samples into [t_start, t_end] to prevent visual drift.
        if interval is not None and len(interval) > 0 and 't_start' in interval.columns and 't_duration' in interval.columns and len(t_values) > 0:
            interval_t_start = interval['t_start'].iloc[0]
            interval_t_duration = interval['t_duration'].iloc[0]
            interval_t_start_unix = float(datetime_to_unix_timestamp(interval_t_start)) if isinstance(interval_t_start, (datetime, pd.Timestamp)) else float(interval_t_start)
            interval_t_end_unix = interval_t_start_unix + float(interval_t_duration)
            in_interval_mask = np.logical_and(t_values >= interval_t_start_unix, t_values <= interval_t_end_unix)
            if np.any(in_interval_mask):
                t_values = t_values[in_interval_mask]
                normalized_channel_df = normalized_channel_df.loc[normalized_channel_df.index[in_interval_mask]]
            elif len(t_values) > 1:
                t_values = np.linspace(interval_t_start_unix, interval_t_end_unix, num=len(t_values), endpoint=True)

        if len(t_values) == 0:
            return graphics_objects

        nPlots: int = len(found_channel_names)
        single_channel_height: float = 1.0 / float(nPlots)

        # Plot each channel with its distinct color
        for i, a_found_channel_name in enumerate(found_channel_names):
            y_values = normalized_channel_df[a_found_channel_name].values
            y_values = y_values * single_channel_height ## scale by the single channel height
            # Get the color for this channel based on its index in channel_names
            channel_index = self.channel_names.index(a_found_channel_name)
            channel_color = self.pen_colors[channel_index]
            pen = pg.mkPen(channel_color, width=self.pen_width)
            # plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=a_found_channel_name)
            plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=a_found_channel_name)
            # plot_data_item = pg.PlotCurveItem(pen=pen, skipFiniteCheck=True)
            plot_item.addItem(plot_data_item)
            plot_data_item.setPos(0, (float(i)*single_channel_height))
            graphics_objects.append(plot_data_item)
        
        # plot_item.setYRange(0, 1, padding=0)

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
            t_end = t_start + t_duration
        
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
            y_min = np.nanmin(np.nanmin(detail_data[col]) for col in channel_columns)
            y_max = np.nanmax(np.nanmax(detail_data[col]) for col in channel_columns)
            # Add padding
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            y_final_min: float = (y_min - y_pad)
            y_final_max: float = (y_max + y_pad)

            # Convert t_start and t_end to Unix timestamps if they're datetime objects
            if isinstance(t_start, (datetime, pd.Timestamp)):
                t_start = datetime_to_unix_timestamp(t_start)
            if isinstance(t_end, (datetime, pd.Timestamp)):
                t_end = datetime_to_unix_timestamp(t_end)
            
            return (t_start, t_end, y_final_min, y_final_max)
        else:
            # No channels found, use default bounds
            # Convert t_start and t_end to Unix timestamps if they're datetime objects
            if isinstance(t_start, (datetime, pd.Timestamp)):
                t_start = datetime_to_unix_timestamp(t_start)
            if isinstance(t_end, (datetime, pd.Timestamp)):
                t_end = datetime_to_unix_timestamp(t_end)
            return (t_start, t_end, 0.0, 1.0)


# ==================================================================================================================================================================================================================================================================================== #
# EEGTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #
class EEGTrackDatasource(ComputableDatasourceMixin, RawProvidingTrackDatasource):
    """TrackDatasource for EEG data with optional LabRecorderXDF / MNE raws (via RawProvidingTrackDatasource).

    Extends RawProvidingTrackDatasource for eeg-specific detail rendering and async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource
    """
    sigSourceComputeStarted = QtCore.Signal()
    sigSourceComputeFinished = QtCore.Signal(bool)

    def __init__(self, intervals_df: pd.DataFrame, eeg_df: pd.DataFrame, custom_datasource_name: Optional[str]=None,
                 max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, parent: Optional[QtCore.QObject] = None,
                 ):
        """Initialize with eeg data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            eeg_df: DataFrame with columns ['t'] and channel columns (e.g., ['AF3', 'F7', 'F3', ...])
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
        """
        if custom_datasource_name is None:
            custom_datasource_name = "EEGTrack"
        super().__init__(intervals_df, detailed_df=eeg_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)

        if (normalization_reference_df is None) and (self.detailed_df is not None):
            normalization_reference_df = self.detailed_df

        # self._detail_renderer = EEGPlotDetailRenderer(
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

        self.ComputableDatasourceMixin_on_init()
        self.clear_computed_result()

        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed


    @property
    def num_sessions(self) -> int:
        """The num_sessions property."""
        return len(self.intervals_df)



    def try_extract_raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[Any]]]]:
        if not self.lab_obj_dict:
            return None
        from phopymnehelper.SavedSessionsProcessor import DataModalityType
        from phopymnehelper.MNE_helpers import up_convert_raw_objects
        from phopymnehelper.EEG_data import EEGData
        out: Dict[str, Optional[List[Any]]] = {}
        for k, lab in self.lab_obj_dict.items():
            if lab is None or not lab.datasets_dict:
                out[k] = None
                continue
            elst = list(lab.datasets_dict.get(DataModalityType.EEG.value, []) or [])
            out[k] = up_convert_raw_objects(elst) if len(elst) > 0 else None
        if not out:
            return None
        _all_eeg_for_montage = [r for _lst in out.values() if _lst for r in _lst]
        if len(_all_eeg_for_montage) > 0:
            EEGData.set_montage(datasets_EEG=_all_eeg_for_montage)
        return cast(Dict[str, Optional[List[Any]]], self._sort_raws_by_meas_start(out))


    def get_detail_renderer(self):
        """Get detail renderer for eeg data."""
        _extra_kw = {'channel_names': self.channel_names} if self.channel_names is not None else {}
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
        return EEGPlotDetailRenderer(pen_width=2, fallback_normalization_mode=self.fallback_normalization_mode, normalization_mode_dict=self.normalization_mode_dict, arbitrary_bounds=self.arbitrary_bounds, normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df, **_extra_kw)


    def exclude_bad_channels(self, bad_channels: List[str]) -> None:
        """Remove bad channels from this datasource's data, normalization config, and renderer channel list.

        Drops the bad-channel columns from ``detailed_df`` and ``normalization_reference_df``,
        updates ``channel_names`` to only good channels, and filters ``normalization_mode_dict``
        so that normalization is computed only over the remaining channels.
        """
        bad_set = set(bad_channels)
        _default_eeg = ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']
        all_channels = self.channel_names if self.channel_names is not None else _default_eeg
        self.channel_names = [ch for ch in all_channels if ch not in bad_set]

        for attr in ('detailed_df', 'normalization_reference_df'):
            df = getattr(self, attr, None)
            if df is not None:
                cols_to_drop = [ch for ch in bad_channels if ch in df.columns]
                if cols_to_drop:
                    setattr(self, attr, df.drop(columns=cols_to_drop))

        if self.normalization_mode_dict is not None:
            updated_norm_dict = {}
            for ch_tuple, mode in self.normalization_mode_dict.items():
                filtered = tuple(ch for ch in ch_tuple if ch not in bad_set)
                if filtered:
                    updated_norm_dict[filtered] = mode
            self.normalization_mode_dict = updated_norm_dict

        logger.info(f'Excluded {len(bad_channels)} bad channels; {len(self.channel_names)} good channels remain: {self.channel_names}')


    def mask_bad_eeg_channels_by_interval_rows(self, bad_channels_per_row: List[List[str]], intervals_df: Optional[pd.DataFrame] = None) -> None:
        active_intervals_df = self.intervals_df if intervals_df is None else intervals_df
        if active_intervals_df is None or len(active_intervals_df) == 0 or len(bad_channels_per_row) == 0:
            return
        for attr in ("detailed_df", "normalization_reference_df"):
            df = getattr(self, attr, None)
            if df is None or "t" not in df.columns:
                continue
            updated_df = df.copy()
            t_values = _coerce_time_series_to_unix(updated_df["t"])
            masked_rows = 0
            masked_channels: set[str] = set()
            for i in range(min(len(active_intervals_df), len(bad_channels_per_row))):
                bad_channels = [ch for ch in (bad_channels_per_row[i] or []) if ch in updated_df.columns]
                if len(bad_channels) == 0:
                    continue
                t_lo, t_hi = _interval_row_to_unix_bounds(active_intervals_df.iloc[i])
                if not np.isfinite(t_lo) or not np.isfinite(t_hi):
                    continue
                interval_mask = (t_values >= t_lo) & (t_values < t_hi) if t_hi > t_lo else (t_values == t_lo)
                if not np.any(interval_mask):
                    continue
                updated_df.loc[interval_mask, bad_channels] = np.nan
                masked_rows += int(np.count_nonzero(interval_mask))
                masked_channels.update(bad_channels)
            if masked_rows > 0:
                setattr(self, attr, updated_df)
                logger.info("Masked %s EEG rows across %s channels on %s using per-interval bad-channel assessments.", masked_rows, len(masked_channels), attr)


    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get cache key for interval (single-row DataFrame or Series)."""
        return super().get_detail_cache_key(interval)


    @function_attributes(short_name=None, tags=['MAIN'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2026-03-02 04:23', related_items=[])
    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: List[pd.DataFrame], custom_datasource_name: Optional[str] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True,
                                   fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None,
                                   lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None,
        **kwargs) -> 'EEGTrackDatasource':
        """Create an EEGTrackDatasource by merging data from multiple sources.
        
        Args:
            intervals_dfs: List of interval DataFrames to merge (each with columns ['t_start', 't_duration'])
            detailed_dfs: List of detailed DataFrames to merge (each with column 't' and EEG channel columns)
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            fallback_normalization_mode: Fallback normalization mode for channels
            normalization_mode_dict: Dictionary mapping channel groups to normalization modes
            arbitrary_bounds: Optional dictionary mapping channel names to (min, max) bounds
            normalize: Whether to normalize channels. Default: True
            normalize_over_full_data: Whether to normalize over full dataset. Default: True
            normalization_reference_df: Optional reference DataFrame for normalization
            
        Returns:
            EEGTrackDatasource instance with merged data
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
        
        # Use merged data as normalization reference if not provided
        if normalization_reference_df is None:
            normalization_reference_df = merged_detailed_df
        
        # Create instance with merged data
        return cls(
            intervals_df=merged_intervals_df,
            eeg_df=merged_detailed_df,
            custom_datasource_name=custom_datasource_name,
            max_points_per_second=max_points_per_second,
            enable_downsampling=enable_downsampling,
            fallback_normalization_mode=fallback_normalization_mode,
            normalization_mode_dict=normalization_mode_dict,
            arbitrary_bounds=arbitrary_bounds,
            normalize=normalize,
            normalize_over_full_data=normalize_over_full_data,
            normalization_reference_df=normalization_reference_df,
            channel_names=channel_names,
            lab_obj_dict=lab_obj_dict,
            raw_datasets_dict=raw_datasets_dict,
        )


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
                """ computes the bad epoch times for EEG/MOTION tracks and optinally adds them to the timeline to preview 

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
                """ plots the bad epochs on the EEG/MOTION views and optionally as a separate track

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
        #                     """ computes the bad epoch times for EEG/MOTION tracks and optinally adds them to the timeline to preview 

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
        #                     """ plots the bad epochs on the EEG/MOTION views and optionally as a separate track

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


    def get_computed_results_for_sess(self, sess_idx: int) -> Dict[types.EEGComputationId, Dict[str, Any]]:
        """ gets the results filtered for only the single session

        Usage:

            desired_sess_idx: int = (eeg_ds.num_sessions - 1) ## last session
            filtered_computed_result: Dict[types.EEGComputationId, Dict[str, Any]] = eeg_ds.get_computed_results_for_sess(sess_idx=desired_sess_idx)
            filtered_computed_result

        """
        assert (sess_idx < self.num_sessions), f"sess_idx: {sess_idx} but max allowed index is (self.num_sessions - 1): {(self.num_sessions - 1)}"
        # computed_result: Dict[types.EEGComputationId, List[Dict[str, Any]]] = self.computed_result # Each list has one entry per eeg_sess
        filtered_computed_result: Dict[types.EEGComputationId, Dict[str, Any]] = {k:v[sess_idx] for k, v in self.computed_result.items()} ## filtered for only the single session
        return filtered_computed_result


    def add_spectrogram_tracks_for_channel_groups(self, spectrogram_channel_groups: Optional[List[SpectrogramChannelGroupConfig]], timeline: "SimpleTimelineWidget", timeline_builder: "TimelineBuilder", *, update_time_range: bool = False, skip_existing_names: bool = True) -> List["EEGSpectrogramTrackDatasource"]:
        """Compute interval-aligned spectrograms from raws, create one ``EEGSpectrogramTrackDatasource`` child per channel group (shared STFT, differing ``group_config``), and append tracks via ``timeline_builder.update_timeline``.

        When ``spectrogram_channel_groups`` is None or empty, adds a single spectrogram track (all channels averaged). Names use prefix ``EEG_Spectrogram_<suffix>`` so dock grouping matches ``stream_to_datasources``.
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
            child: EEGSpectrogramTrackDatasource = EEGSpectrogramTrackDatasource(intervals_df=self.intervals_df.copy(), spectrogram_result=None, spectrogram_results=spec_results, custom_datasource_name=track_name, group_config=gcfg, channel_group_presets=presets, lab_obj_dict=self.lab_obj_dict, raw_datasets_dict=self.raw_datasets_dict, parent=self)
            created.append(child)
        if getattr(self, "_spectrogram_child_datasources", None) is None:
            self._spectrogram_child_datasources = []
        self._spectrogram_child_datasources.extend(created)
        if len(created) > 0:
            timeline_builder.update_timeline(timeline, [*created], update_time_range=update_time_range)
        return created



# ==================================================================================================================================================================================================================================================================================== #
# EEGFPTrackDatasource - Historical EEG track with band-limited GFP detail view
# ==================================================================================================================================================================================================================================================================================== #


class EEGFPTrackDatasource(EEGTrackDatasource):
    """Same data model as :class:`EEGTrackDatasource` (intervals + ``detailed_df`` with ``t`` and channel columns),
    but detail overlays use :class:`~pypho_timeline.rendering.detail_renderers.line_power_gfp_detail_renderer.LinePowerGFPDetailRenderer`
    (theta–gamma GFP lanes). Use for retrospective timelines; live LSL uses :class:`~pypho_timeline.rendering.datasources.specific.lsl.LiveEEGFPTrackDatasource`.

    GFP band-pass uses the acquisition sample rate: taken from ``gfp_nominal_srate``, else the first ``sfreq`` in ``raw_datasets_dict``, else inferred from downsampled ``t`` (often too low for alpha–gamma). Pass ``raw_datasets_dict`` from the parent EEG datasource when possible.

    Usage:
        After a timeline and an :class:`EEGTrackDatasource` already exist (e.g. from ``TimelineBuilder``), add a GFP track from the same data::

            from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
            from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource, EEGFPTrackDatasource

            assert isinstance(eeg_ds, EEGTrackDatasource)
            gfp_ds = EEGFPTrackDatasource(intervals_df=eeg_ds.intervals_df.copy(), eeg_df=eeg_ds.detailed_df, custom_datasource_name=f"{eeg_ds.custom_datasource_name}_GFP", channel_names=eeg_ds.channel_names, max_points_per_second=eeg_ds.max_points_per_second, enable_downsampling=eeg_ds.enable_downsampling, lab_obj_dict=getattr(eeg_ds, "lab_obj_dict", None), raw_datasets_dict=getattr(eeg_ds, "raw_datasets_dict", None))
            track_widget, _root, gfp_plot, _dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(name=gfp_ds.custom_datasource_name, dockSize=(500, 120), dockAddLocationOpts=["bottom"], sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA)
            ref_name = eeg_ds.custom_datasource_name
            if ref_name in timeline.ui.matplotlib_view_widgets:
                ref_plot = timeline.ui.matplotlib_view_widgets[ref_name].getRootPlotItem()
                x0, x1 = ref_plot.getViewBox().viewRange()[0]
                gfp_plot.setXRange(x0, x1, padding=0)
            gfp_plot.setYRange(0, 5, padding=0)
            gfp_plot.hideAxis("left")
            timeline.add_track(gfp_ds, name=gfp_ds.custom_datasource_name, plot_item=gfp_plot)
    """

    def __init__(self, intervals_df: pd.DataFrame, eeg_df: pd.DataFrame, custom_datasource_name: Optional[str] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True, fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None, channel_names: Optional[List[str]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, gfp_filter_order: int = 4, gfp_n_bootstrap: int = 100, gfp_baseline_start: Optional[float] = None, gfp_baseline_end: float = 0.0, gfp_show_confidence: bool = False, gfp_line_width: float = 0.5, gfp_nominal_srate: Optional[float] = None, parent: Optional[QtCore.QObject] = None):
        if custom_datasource_name is None:
            custom_datasource_name = "EEGFPTrack"
        self._gfp_filter_order = int(gfp_filter_order)
        self._gfp_n_bootstrap = int(gfp_n_bootstrap)
        self._gfp_baseline_start = gfp_baseline_start
        self._gfp_baseline_end = gfp_baseline_end
        self._gfp_show_confidence = bool(gfp_show_confidence)
        self._gfp_line_width = float(gfp_line_width)
        self._gfp_nominal_srate = float(gfp_nominal_srate) if (gfp_nominal_srate is not None and gfp_nominal_srate > 0) else _first_sfreq_from_raw_datasets_dict(raw_datasets_dict)
        super().__init__(intervals_df=intervals_df, eeg_df=eeg_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, fallback_normalization_mode=fallback_normalization_mode, normalization_mode_dict=normalization_mode_dict, arbitrary_bounds=arbitrary_bounds, normalize=normalize, normalize_over_full_data=normalize_over_full_data, normalization_reference_df=normalization_reference_df, channel_names=channel_names, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)



    def get_detail_renderer(self):
        from pypho_timeline.rendering.detail_renderers.line_power_gfp_detail_renderer import LinePowerGFPDetailRenderer
        _extra_kw = dict(channel_names=self.channel_names) if self.channel_names is not None else {}
        return LinePowerGFPDetailRenderer(live_mode=False, filter_order=self._gfp_filter_order, n_bootstrap=self._gfp_n_bootstrap, baseline_start=self._gfp_baseline_start, baseline_end=self._gfp_baseline_end, show_confidence=self._gfp_show_confidence, line_width=self._gfp_line_width, nominal_srate=self._gfp_nominal_srate, **_extra_kw)


# ==================================================================================================================================================================================================================================================================================== #
# EEGSpectrogramDetailRenderer - Renders spectrogram (t x freq) as ImageItem.
# ==================================================================================================================================================================================================================================================================================== #
class EEGSpectrogramDetailRenderer(DetailRenderer):
    """Detail renderer for EEG spectrogram tracks. Displays spectrogram as a 2D image (time x frequency, log power).

    Expects detail_data to be a dict compatible with EEGComputations.raw_spectogram_working output:
    at least 't' (1D), 'freqs' (1D), and 'Sxx' (xarray or ndarray: channels × freqs × times, or freqs × times).
    """

    def __init__(self, freq_min: float = 1.0, freq_max: float = 40.0, group_channels: Optional[List[str]] = None, **kwargs):
        """Initialize the spectrogram renderer.

        Args:
            freq_min: Lower frequency bound (Hz) for display. Default: 1.0
            freq_max: Upper frequency bound (Hz) for display. Default: 40.0
            group_channels: If set, only these channel names are averaged for this track.
                When None, falls back to channel_visibility / all-channels averaging.
        """
        DetailRenderer.__init__(self, **kwargs)
        self.freq_min = freq_min
        self.freq_max = freq_max
        self.group_channels: Optional[List[str]] = group_channels


    def _get_sxx_2d(self, detail_data: Dict) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Extract (freqs, t, Sxx_2d) from spectrogram dict. Sxx_2d is (n_freqs, n_times).

        Channel selection priority:
        1. If group_channels is set, use only those channels (intersected with available ch_names
           and further filtered by channel_visibility if present).
        2. Otherwise fall back to channel_visibility filtering.
        3. Otherwise average over all channels.
        """
        if not detail_data or not isinstance(detail_data, dict):
            return None
        freqs = detail_data.get('freqs')
        t = detail_data.get('t')
        Sxx = detail_data.get('Sxx')
        if freqs is None or t is None or Sxx is None:
            return None
        freqs = np.asarray(freqs)
        t = np.asarray(t)
        if hasattr(Sxx, 'values'):
            Sxx = Sxx.values
        Sxx = np.asarray(Sxx)
        if Sxx.ndim == 3:
            ch_names = detail_data.get('ch_names')
            if ch_names is not None and len(ch_names) == Sxx.shape[0]:
                if self.group_channels is not None:
                    group_set = set(self.group_channels)
                    has_visibility = hasattr(self, 'channel_visibility') and self.channel_visibility
                    indices = [i for i, ch in enumerate(ch_names) if ch in group_set and (not has_visibility or self.channel_visibility.get(ch, True))]
                elif hasattr(self, 'channel_visibility') and self.channel_visibility:
                    indices = [i for i, ch in enumerate(ch_names) if self.channel_visibility.get(ch, True)]
                else:
                    indices = None
                if indices is not None and indices:
                    Sxx = np.nanmean(Sxx[indices, :, :], axis=0)
                else:
                    Sxx = np.nanmean(Sxx, axis=0)
            else:
                Sxx = np.nanmean(Sxx, axis=0)
        if Sxx.ndim != 2 or Sxx.shape[0] != len(freqs) or Sxx.shape[1] != len(t):
            return None
        return (freqs, t, Sxx)


    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render spectrogram as a single ImageItem (time x frequency, log power)."""
        logger.debug(f"EEGSpectrogramDetailRenderer.render_detail(plot_item, interval, detail_data)")
        if detail_data is None:
            return []
        out = self._get_sxx_2d(detail_data)
        if out is None:
            return []
        freqs, t, Sxx = out
        img = 10.0 * np.log10(Sxx + 1e-12)
        freq_mask = (freqs >= self.freq_min) & (freqs <= self.freq_max)
        if not np.any(freq_mask):
            return []
        freqs_sel = freqs[freq_mask]
        img_sel = img[freq_mask, :]
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_start = datetime_to_unix_timestamp(t_start)
        t_start = float(t_start)
        t_duration = float(t_duration)
        freq_min, freq_max = float(freqs_sel.min()), float(freqs_sel.max())
        img_item: pg.ImageItem = pg.ImageItem(img_sel)
        # Use y=0..1 so the image is visible with the timeline's default setYRange(0, 1) for all tracks
        img_item.setRect(QtCore.QRectF(t_start, 0.0, t_duration, 1.0))
        img_item.setColorMap(pg.colormap.get('viridis'))
        plot_item.addItem(img_item)
        return [img_item]


    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove spectrogram graphics objects."""
        if graphics_objects is None:
            return
        for obj in graphics_objects:
            if obj is None:
                continue
            try:
                plot_item.removeItem(obj)
                if hasattr(obj, 'setParentItem'):
                    obj.setParentItem(None)
            except (AttributeError, RuntimeError):
                pass


    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Return (x_min, x_max, y_min, y_max) for the detail view (time x frequency)."""
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        t_end = t_start + t_duration
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_start = datetime_to_unix_timestamp(t_start)
        if isinstance(t_end, (datetime, pd.Timestamp)):
            t_end = datetime_to_unix_timestamp(t_end)
        x_min = float(t_start)
        x_max = float(t_end)
        if detail_data is None or not isinstance(detail_data, dict):
            return (x_min, x_max, self.freq_min, self.freq_max)
        freqs = detail_data.get('freqs')
        if freqs is None:
            return (x_min, x_max, self.freq_min, self.freq_max)
        freqs = np.asarray(freqs)
        freq_mask = (freqs >= self.freq_min) & (freqs <= self.freq_max)
        if not np.any(freq_mask):
            return (x_min, x_max, self.freq_min, self.freq_max)
        f_min = float(freqs[freq_mask].min())
        f_max = float(freqs[freq_mask].max())
        return (x_min, x_max, f_min, f_max)


    ## override `_trigger_visibility_render` to recompute the correct average when channel visibility is updated
    def _trigger_visibility_render(self):
        """Helper method to clear all visible detail graphics and trigger re-render after visibility changes."""
        # Clear all visible detail graphics
        logger.warning(f"EEGSpectrogramDetailRenderer[{self.track_id}] _trigger_visibility_render()")
        visible_cache_keys = list(self.visible_intervals)
        logger.debug(f"EEGSpectrogramDetailRenderer[{self.track_id}] Clearing {len(visible_cache_keys)} intervals for re-render after visibility change")
        
        for cache_key in visible_cache_keys:
            self._clear_detail(cache_key)
        
        # Clear visible_intervals so update_viewport() will treat all intervals as new and re-fetch/re-render them
        self.visible_intervals.clear() ## this seems uneeded and relies on update_viewport to rebuild them
        logger.debug(f"EEGSpectrogramDetailRenderer[{self.track_id}] Cleared visible_intervals to force re-fetch on next update_viewport()")
        
        # Trigger viewport update to re-render with new visibility
        # This will re-fetch intervals and render with filtered channels
        if self.plot_item is not None:
            viewbox = self.plot_item.getViewBox()
            if viewbox is not None:
                x_range, y_range = viewbox.viewRange()
                if len(x_range) == 2:
                    self.update_viewport(x_range[0], x_range[1])




# ==================================================================================================================================================================================================================================================================================== #
# EEGSpectrogramTrackDatasource
# ==================================================================================================================================================================================================================================================================================== #
class EEGSpectrogramTrackDatasource(ComputableDatasourceMixin, RawProvidingTrackDatasource):
    """TrackDatasource that shares intervals with an EEG track and displays spectrogram detail (from EEGComputations.raw_spectogram_working). Optional lab/raw handles via RawProvidingTrackDatasource."""
    sigSourceComputeStarted = QtCore.Signal()
    sigSourceComputeFinished = QtCore.Signal(bool)

    def __init__(self, intervals_df: pd.DataFrame, spectrogram_result: Optional[Dict[str, Any]] = None, custom_datasource_name: Optional[str] = None, spectrogram_results: Optional[List[Optional[Dict[str, Any]]]] = None,
                 freq_min: float = 1.0, freq_max: float = 40.0, group_config: Optional[SpectrogramChannelGroupConfig] = None, channel_group_presets: Optional[List[SpectrogramChannelGroupConfig]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, parent: Optional[QtCore.QObject] = None):
        """Initialize with intervals and precomputed spectrogram result(s).

        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] (same as EEG track).
            spectrogram_result: Single spectrogram dict from EEGComputations.raw_spectogram_working (used when one interval).
            custom_datasource_name: Name for this datasource (e.g. EEG_Spectrogram_StreamName).
            spectrogram_results: Optional list of spectrogram dicts, one per row in intervals_df (for merged multi-interval case).
            freq_min, freq_max: Passed to EEGSpectrogramDetailRenderer.
            group_config: Optional channel group config; when set, the renderer averages only over these channels.
            channel_group_presets: Optional list of preset groups (same shape as stream build ``spectrogram_channel_groups``) for the options panel preset combo.
        """
        super().__init__(intervals_df=intervals_df, detailed_df=None, custom_datasource_name=custom_datasource_name or "EEG_Spectrogram", max_points_per_second=None, enable_downsampling=False, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, parent=parent)
        if spectrogram_results is None and spectrogram_result is not None:
            spectrogram_results = [spectrogram_result]
            spectrogram_result = None
        self._spectrogram_result = spectrogram_result
        self._spectrogram_results = list(spectrogram_results) if spectrogram_results is not None else None
        self._freq_min = freq_min
        self._freq_max = freq_max
        self._group_config = group_config
        self._channel_group_presets = channel_group_presets
        self.ComputableDatasourceMixin_on_init()


    @property
    def channel_group_presets(self) -> Optional[List[SpectrogramChannelGroupConfig]]:
        return self._channel_group_presets


    @property
    def spectrogram_freq_min(self) -> float:
        return self._freq_min


    @property
    def spectrogram_freq_max(self) -> float:
        return self._freq_max


    @property
    def group_config(self) -> Optional[SpectrogramChannelGroupConfig]:
        return self._group_config


    def get_spectrogram_ch_names(self) -> List[str]:
        """Channel names from the stored spectrogram dict (``ch_names``), or empty if missing."""
        all_channel_names: set[str] = set()
        details = self._spectrogram_results if self._spectrogram_results is not None else ([self._spectrogram_result] if self._spectrogram_result is not None else [])
        for detail in details:
            if not detail or not isinstance(detail, dict):
                continue
            ch_names = detail.get("ch_names")
            if ch_names is None:
                continue
            all_channel_names.update(list(ch_names))
        return sorted(all_channel_names)


    def set_spectrogram_display(self, freq_min: float, freq_max: float) -> None:
        """Update displayed frequency bounds for the spectrogram detail view."""
        self._freq_min = float(freq_min)
        self._freq_max = float(freq_max)


    def set_group_config(self, cfg: Optional[SpectrogramChannelGroupConfig]) -> None:
        """Replace channel group config. When ``cfg`` is set, stores a copy so preset lists are not mutated in place."""
        if cfg is None:
            self._group_config = None
            return
        self._group_config = SpectrogramChannelGroupConfig(name=cfg.name, channels=list(cfg.channels))


    def fetch_detailed_data(self, interval: pd.Series) -> Any:
        """Return the spectrogram dict for this interval."""
        if self._spectrogram_results is not None:
            t_start = interval.get('t_start')
            t_duration = interval.get('t_duration')
            match = (self.intervals_df['t_start'] == t_start) & (self.intervals_df['t_duration'] == t_duration)
            pos = np.flatnonzero(match)
            if len(pos) > 0 and pos[0] < len(self._spectrogram_results):
                return self._spectrogram_results[int(pos[0])]
            logger.debug("EEGSpectrogramTrackDatasource[%s] missing spectrogram result for interval t_start=%s t_duration=%s.", self.custom_datasource_name, t_start, t_duration)
            return None
        return self._spectrogram_result


    def get_detail_renderer(self) -> EEGSpectrogramDetailRenderer:
        """Return the spectrogram detail renderer."""
        group_channels = self._group_config.channels if self._group_config is not None else None
        return EEGSpectrogramDetailRenderer(freq_min=self._freq_min, freq_max=self._freq_max, group_channels=group_channels)


    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        return super().get_detail_cache_key(interval)


    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], spectrogram_results: List[Optional[Dict[str, Any]]], custom_datasource_name: Optional[str] = None, freq_min: float = 1.0, freq_max: float = 40.0, group_config: Optional[SpectrogramChannelGroupConfig] = None, channel_group_presets: Optional[List[SpectrogramChannelGroupConfig]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None) -> 'EEGSpectrogramTrackDatasource':
        """Create one EEGSpectrogramTrackDatasource from multiple (intervals_df, spectrogram_result) pairs."""
        if not intervals_dfs or not spectrogram_results:
            raise ValueError("intervals_dfs and spectrogram_results must be non-empty")
        merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start').reset_index(drop=True)
        if len(merged_intervals_df) != len(spectrogram_results):
            raise ValueError("Merged interval row count and spectrogram_results length must match")
        return cls(intervals_df=merged_intervals_df, spectrogram_result=None, custom_datasource_name=custom_datasource_name, spectrogram_results=spectrogram_results, freq_min=freq_min, freq_max=freq_max, group_config=group_config, channel_group_presets=channel_group_presets, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict)



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
        
        active_compute_goals_list = ("spectogram",)

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



        ## ACTIVE
        # rep, lst = compute_multiraw_spectrogram_results(self.intervals_df, self.raw_datasets_dict)
        # self._spectrogram_result = rep
        # self._spectrogram_results = lst


        # eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=("spectogram",))
        # self._spectrogram_result = eeg_comps_result["spectogram"]
        # self.on_recompute_finished()

        self.on_compute_finished()


    def on_compute_finished(self, **kwargs):
        """ called to indicate that a recompute is finished """
        was_success = False

        self._spectrogram_results = self.computed_result.get('spectogram', None)
        if self._spectrogram_results is not None:
            self._spectrogram_result = None

        if self._spectrogram_results is not None:
            was_success = any(x is not None for x in self._spectrogram_results)
        if not was_success:
            was_success = self._spectrogram_result is not None
        logger.info(f'.on_compute_finished(was_success: {was_success})')
        self.sigSourceComputeFinished.emit(was_success)



__all__ = ['SpectrogramChannelGroupConfig', 'EMOTIV_EPOC_X_SPECTROGRAM_GROUPS', 'EEGPlotDetailRenderer', 'EEGTrackDatasource', 'EEGFPTrackDatasource', 'EEGSpectrogramDetailRenderer', 'EEGSpectrogramTrackDatasource', 'aligned_chronological_raws_for_intervals', 'compute_multiraw_spectrogram_results']

