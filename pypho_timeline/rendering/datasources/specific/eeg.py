import numpy as np
import pandas as pd
# from qtpy import QtWidgets, QtCore
from typing import Dict, List, Mapping, Tuple, Optional, Callable, Union, Any, Sequence
from datetime import datetime
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp

# ==================================================================================================================================================================================================================================================================================== #
# EEGPlotDetailRenderer - Renders eeg data as line plots.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode, ChannelNormalizationModeNormalizingMixin


## NOTE: Currently inherits directly from DetailRenderer protocol. GenericPlotDetailRenderer is designed
## to wrap functions rather than for traditional inheritance. MotionPlotDetailRenderer follows the same pattern.
class EEGPlotDetailRenderer(ChannelNormalizationModeNormalizingMixin, DetailRenderer):
    """Detail renderer for eeg tracks that displays eeg channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns
    (e.g., ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']).

    Usage:
        from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer, EEGTrackDatasource

    """
    
    def __init__(self, pen_width=2, channel_names=['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'], pen_colors=None,
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

        # Filter channels based on visibility if channel_visibility is set
        if hasattr(self, 'channel_visibility') and self.channel_visibility:
            found_channel_names = [ch for ch in found_channel_names if self.channel_visibility.get(ch, True)]

        # Normalize channel columns using shared helper
        normalized_channel_df, (y_min, y_max) = self.compute_normalized_channels(detail_df=df_sorted, channel_names=found_channel_names)

        # Extract t_values aligned with normalized_channel_df's index to ensure shape matches
        # normalized_channel_df may have fewer rows due to index intersection during normalization
        t_col_aligned = df_sorted.loc[normalized_channel_df.index, 't']
        if pd.api.types.is_datetime64_any_dtype(t_col_aligned):
            # Convert datetime to Unix timestamps
            t_values = t_col_aligned.apply(lambda x: datetime_to_unix_timestamp(x) if isinstance(x, (datetime, pd.Timestamp)) else x).values
        else:
            t_values = t_col_aligned.values

        # Plot each channel with its distinct color
        for a_found_channel_name in found_channel_names:
            y_values = normalized_channel_df[a_found_channel_name].values
            # Get the color for this channel based on its index in channel_names
            channel_index = self.channel_names.index(a_found_channel_name)
            channel_color = self.pen_colors[channel_index]
            pen = pg.mkPen(channel_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=a_found_channel_name)
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        
        return graphics_objects
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove eeg plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
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
            y_min = min(detail_data[col].min() for col in channel_columns)
            y_max = max(detail_data[col].max() for col in channel_columns)
            # Add padding
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            
            # Convert t_start and t_end to Unix timestamps if they're datetime objects
            if isinstance(t_start, (datetime, pd.Timestamp)):
                t_start = datetime_to_unix_timestamp(t_start)
            if isinstance(t_end, (datetime, pd.Timestamp)):
                t_end = datetime_to_unix_timestamp(t_end)
            
            return (t_start, t_end, (y_min - y_pad), (y_max + y_pad))
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
class EEGTrackDatasource(IntervalProvidingTrackDatasource):
    """Example TrackDatasource for eeg data.
    
    Inherits from IntervalProvidingTrackDatasource and implements eeg-specific
    detail rendering for displaying eeg data with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource
    """
    
    def __init__(self, intervals_df: pd.DataFrame, eeg_df: pd.DataFrame, custom_datasource_name: Optional[str]=None,
                 max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None,
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
        super().__init__(intervals_df, detailed_df=eeg_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling)

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

        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed
    
    def get_detail_renderer(self):
        """Get detail renderer for eeg data."""
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
            return EEGPlotDetailRenderer(
                pen_width=2,
                fallback_normalization_mode=self.fallback_normalization_mode,
                normalization_mode_dict=self.normalization_mode_dict,
                arbitrary_bounds=self.arbitrary_bounds,
                normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df,                
            )
        return EEGPlotDetailRenderer(
            pen_width=2,
            fallback_normalization_mode=self.fallback_normalization_mode,
            normalization_mode_dict=self.normalization_mode_dict,
            arbitrary_bounds=self.arbitrary_bounds,
            normalize=self.normalize, normalize_over_full_data=self.normalize_over_full_data, normalization_reference_df=self.normalization_reference_df,
        )


    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        # Delegate to base implementation which handles datetime/timedelta correctly
        # and includes the datasource name to avoid collisions across tracks.
        return super().get_detail_cache_key(interval)

    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: List[pd.DataFrame], custom_datasource_name: Optional[str] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True, fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None, normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None) -> 'EEGTrackDatasource':
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
            normalization_reference_df=normalization_reference_df
        )


__all__ = ['EEGPlotDetailRenderer', 'EEGTrackDatasource']

