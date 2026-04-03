from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from qtpy import QtCore
from typing import Dict, List, Mapping, Tuple, Optional, Callable, Union, Any, Sequence, TYPE_CHECKING
from datetime import datetime
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, RawProvidingTrackDatasource, ComputableDatasourceMixin
if TYPE_CHECKING:
    import mne
    from phopymnehelper.xdf_files import LabRecorderXDF
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp

from pypho_timeline.utils.logging_util import get_rendering_logger
logger = get_rendering_logger(__name__)


def _first_nonempty_raw_list_from_dict(raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> List[Any]:
    if raw_datasets_dict is None:
        return []
    for v in raw_datasets_dict.values():
        if v is not None and len(v) > 0:
            return v
    return []


def first_chronological_raw_from_datasets_dict(raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> Any:
    raws = RawProvidingTrackDatasource.get_sorted_and_extracted_raws(raw_datasets_dict)
    return raws[0] if raws else None


def compute_multiraw_spectrogram_results(intervals_df: pd.DataFrame, raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> Tuple[Optional[Dict[str, Any]], Optional[List[Optional[Dict[str, Any]]]]]:
    from phopymnehelper.analysis.computations.eeg_registry import run_eeg_computations_graph, session_fingerprint_for_raw_or_path
    raws = RawProvidingTrackDatasource.get_sorted_and_extracted_raws(raw_datasets_dict)
    n_iv = len(intervals_df)
    if n_iv == 0 or not raws:
        return None, None
    n = min(len(raws), n_iv)
    if len(raws) != n_iv:
        logger.warning("EEG spectrogram: raw count (%s) != interval count (%s); using %s chronological raws aligned to interval rows; excess raws or intervals have no matching spectrogram.", len(raws), n_iv, n)
    out: List[Optional[Dict[str, Any]]] = [None] * n_iv
    for i in range(n):
        raw = raws[i]
        eeg_comps_result = run_eeg_computations_graph(raw, session=session_fingerprint_for_raw_or_path(raw), goals=("spectogram",))
        out[i] = eeg_comps_result.get("spectogram")
    rep = next((x for x in out if x is not None), None)
    return rep, out


@dataclass
class SpectrogramChannelGroupConfig:
    """Defines a named group of EEG channels to average for one spectrogram track."""
    name: str
    channels: List[str]


EMOTIV_EPOC_X_SPECTROGRAM_GROUPS: List[SpectrogramChannelGroupConfig] = [
    # SpectrogramChannelGroupConfig(name='Frontal-L', channels=['AF3', 'F7', 'FC5', 'F3']),
    # SpectrogramChannelGroupConfig(name='Frontal-R', channels=['AF4', 'F8', 'FC6', 'F4']),
    # SpectrogramChannelGroupConfig(name='Posterior-L', channels=['T7', 'P7', 'O1']),
    # SpectrogramChannelGroupConfig(name='Posterior-R', channels=['T8', 'P8', 'O2']),
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
        from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer, EEGTrackDatasource

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
        if pd.api.types.is_datetime64_any_dtype(t_col_aligned):
            t_values = np.asarray(datetime_to_unix_timestamp(t_col_aligned.to_list()), dtype=float)
        else:
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

        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed


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
        return self._sort_raws_by_meas_start(out)


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
                    self.raw_datasets_dict = self.get_sorted_and_extracted_raws(self.raw_datasets_dict) ## try sort and extract

        self.sigSourceComputeStarted.emit()
        pass
        self.on_compute_finished()


    def on_compute_finished(self, **kwargs):
        """ called to indicate that a recompute is finished """
        was_success: bool = True # (self._spectrogram_result is not None)
        logger.info(f'.on_compute_finished(was_success: {was_success})')
        self.sigSourceComputeFinished.emit(was_success)




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

    def __init__(self, intervals_df: pd.DataFrame, spectrogram_result: Dict, custom_datasource_name: Optional[str] = None, spectrogram_results: Optional[List[Dict]] = None,
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
        self._spectrogram_result = spectrogram_result
        self._spectrogram_results = spectrogram_results
        self._freq_min = freq_min
        self._freq_max = freq_max
        self._group_config = group_config
        self._channel_group_presets = channel_group_presets


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
        detail: Any = None
        if self._spectrogram_results is not None and len(self._spectrogram_results) > 0:
            detail = self._spectrogram_results[0]
        else:
            detail = self._spectrogram_result
        if not detail or not isinstance(detail, dict):
            return []
        ch = detail.get('ch_names')
        if ch is None:
            return []
        return list(ch)


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
            return self._spectrogram_results[0] if self._spectrogram_results else None
        return self._spectrogram_result


    def get_detail_renderer(self) -> EEGSpectrogramDetailRenderer:
        """Return the spectrogram detail renderer."""
        group_channels = self._group_config.channels if self._group_config is not None else None
        return EEGSpectrogramDetailRenderer(freq_min=self._freq_min, freq_max=self._freq_max, group_channels=group_channels)


    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        return super().get_detail_cache_key(interval)


    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], spectrogram_results: List[Dict], custom_datasource_name: Optional[str] = None, freq_min: float = 1.0, freq_max: float = 40.0, group_config: Optional[SpectrogramChannelGroupConfig] = None, channel_group_presets: Optional[List[SpectrogramChannelGroupConfig]] = None, lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None) -> 'EEGSpectrogramTrackDatasource':
        """Create one EEGSpectrogramTrackDatasource from multiple (intervals_df, spectrogram_result) pairs."""
        if not intervals_dfs or not spectrogram_results:
            raise ValueError("intervals_dfs and spectrogram_results must be non-empty")
        if len(intervals_dfs) != len(spectrogram_results):
            raise ValueError("intervals_dfs and spectrogram_results must have the same length")
        merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start')
        first_result = spectrogram_results[0]
        return cls(intervals_df=merged_intervals_df, spectrogram_result=first_result, custom_datasource_name=custom_datasource_name, spectrogram_results=spectrogram_results, freq_min=freq_min, freq_max=freq_max, group_config=group_config, channel_group_presets=channel_group_presets, lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict)



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
        self.sigSourceComputeStarted.emit()
        rep, lst = compute_multiraw_spectrogram_results(self.intervals_df, self.raw_datasets_dict)
        self._spectrogram_result = rep
        self._spectrogram_results = lst
        self.on_compute_finished()


    def on_compute_finished(self, **kwargs):
        """ called to indicate that a recompute is finished """
        was_success = False
        if self._spectrogram_results is not None:
            was_success = any(x is not None for x in self._spectrogram_results)
        if not was_success:
            was_success = self._spectrogram_result is not None
        logger.info(f'.on_compute_finished(was_success: {was_success})')
        self.sigSourceComputeFinished.emit(was_success)



__all__ = ['SpectrogramChannelGroupConfig', 'EMOTIV_EPOC_X_SPECTROGRAM_GROUPS', 'EEGPlotDetailRenderer', 'EEGTrackDatasource', 'EEGSpectrogramDetailRenderer', 'EEGSpectrogramTrackDatasource', 'compute_multiraw_spectrogram_results', 'first_chronological_raw_from_datasets_dict']

