"""Channel normalization helpers for timeline renderers.

This module defines a shared ChannelNormalizationMode enum and helpers
for normalizing multi-channel time series data in a consistent way.

Typical usage patterns:

    from pypho_timeline.rendering.helpers.normalization import (
        ChannelNormalizationMode, normalize_channels
    )

    # Motion example: group accelerometer and gyro channels separately
    motion_normalization_mode_dict = {
        ('AccX', 'AccY', 'AccZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
        ('GyroX', 'GyroY', 'GyroZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
    }

    # EEG example: normalize each channel independently
    eeg_normalization_mode_dict = {
        ('AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8',
         'FC6', 'F4', 'F8', 'AF4'): ChannelNormalizationMode.INDIVIDUAL,
    }

The helpers are intentionally renderer-agnostic to avoid circular imports.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyqtgraph as pg

from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log
from phopymnehelper.helpers.dataframe_accessor_helpers import MaskedValidDataFrameAccessor

logger = get_rendering_logger(__name__)


class ChannelNormalizationMode(Enum):
    """Specifies how multiple channels are normalized for plotting."""

    NONE = auto()              # No normalization; plot raw values
    GROUPMINMAXRANGE = auto()  # Normalize all channels in a group together from shared [nanmin, nanmax]
    INDIVIDUAL = auto()        # Normalize each channel individually to [0, 1] from its own nanmin/nanmax
    ARBITRARY = auto()         # Normalize using arbitrary (specified) bounds per channel


def build_channel_mode_map(channel_names: Sequence[str], normalization_mode_dict: Optional[Mapping[Iterable[str], ChannelNormalizationMode]], default_mode: ChannelNormalizationMode) -> Dict[str, ChannelNormalizationMode]:
    """Build per-channel normalization mode map from group dict and default.

    Args:
        channel_names: Channels that will be rendered.
        normalization_mode_dict: Mapping from iterable-of-channel-names (usually tuples)
            to ChannelNormalizationMode.
        default_mode: Mode to use for channels not covered by any group.
    """
    channel_mode_map: Dict[str, ChannelNormalizationMode] = {name: default_mode for name in channel_names}

    if normalization_mode_dict is None:
        return channel_mode_map

    for group_channels, mode in normalization_mode_dict.items():
        for ch in group_channels:
            if ch in channel_mode_map:
                channel_mode_map[ch] = mode

    return channel_mode_map


def _safe_min_max(values: np.ndarray) -> Tuple[float, float]:
    """Return nan-safe (min, max) with sensible defaults."""
    if values.size == 0:
        return 0.0, 1.0

    v_min = float(np.nanmin(values))
    v_max = float(np.nanmax(values))
    if not np.isfinite(v_min) or not np.isfinite(v_max):
        return 0.0, 1.0
    if v_max == v_min:
        # Avoid division by zero; treat as small non-zero range
        return v_min, v_min + 1.0
    return v_min, v_max


def normalize_channels(df: pd.DataFrame, channel_names: Sequence[str], default_mode: ChannelNormalizationMode, normalization_mode_dict: Optional[Mapping[Iterable[str], ChannelNormalizationMode]] = None, arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None) -> pd.DataFrame:
    """Return a normalized view of the specified channels according to modes.

    Args:
        df: Source dataframe containing the channel columns.
        channel_names: Channels to normalize.
        default_mode: Mode used when a channel is not covered by any group in
            normalization_mode_dict.
        normalization_mode_dict: Optional mapping from iterable-of-channel-names
            to ChannelNormalizationMode. Keys are typically tuples of channel
            names representing a logical group (e.g., accel vs gyro).
        arbitrary_bounds: Optional mapping from channel name to (min, max)
            bounds used when the effective mode is ARBITRARY. If bounds are
            missing for a channel, a default range of [0.0, 1.0] is used.

    Returns:
        A new DataFrame containing only the specified channel columns,
        normalized according to their effective mode.
    """
    if not channel_names:
        return pd.DataFrame(index=df.index)

    channel_df = df[list(channel_names)].astype(float)
    channel_mode_map = build_channel_mode_map(channel_names, normalization_mode_dict, default_mode)
    arbitrary_bounds = arbitrary_bounds or {}

    # Pre-compute group min/max for GROUPMINMAXRANGE groups to avoid redundant work
    group_bounds: Dict[Tuple[str, ...], Tuple[float, float]] = {}
    if normalization_mode_dict is not None:
        for group_channels, mode in normalization_mode_dict.items():
            group_tuple = tuple(ch for ch in group_channels if ch in channel_df.columns)
            if not group_tuple:
                continue
            if mode is ChannelNormalizationMode.GROUPMINMAXRANGE and group_tuple not in group_bounds:
                group_values = channel_df[list(group_tuple)].values
                g_min, g_max = _safe_min_max(group_values)
                group_bounds[group_tuple] = (g_min, g_max)

    normalized_cols: Dict[str, pd.Series] = {}

    for ch in channel_names:
        series = channel_df[ch].values
        mode = channel_mode_map.get(ch, default_mode)

        if mode is ChannelNormalizationMode.NONE:
            normalized_cols[ch] = pd.Series(series, index=channel_df.index)
            continue

        if mode is ChannelNormalizationMode.ARBITRARY:
            bounds = arbitrary_bounds.get(ch, (0.0, 1.0))
            b_min, b_max = bounds
            if b_max == b_min:
                b_max = b_min + 1.0
            normalized = (series - b_min) / float(b_max - b_min)
            normalized_cols[ch] = pd.Series(normalized, index=channel_df.index)
            continue

        if mode is ChannelNormalizationMode.GROUPMINMAXRANGE and normalization_mode_dict is not None:
            # Find the first group that contains this channel
            applied = False
            for group_channels, group_mode in normalization_mode_dict.items():
                if group_mode is not ChannelNormalizationMode.GROUPMINMAXRANGE:
                    continue
                if ch in group_channels:
                    group_tuple = tuple(gc for gc in group_channels if gc in channel_df.columns)
                    if not group_tuple:
                        break
                    g_min, g_max = group_bounds.get(group_tuple, _safe_min_max(channel_df[list(group_tuple)].values))
                    if g_max == g_min:
                        g_max = g_min + 1.0
                    normalized = (series - g_min) / float(g_max - g_min)
                    normalized_cols[ch] = pd.Series(normalized, index=channel_df.index)
                    applied = True
                    break

            if applied:
                continue
            # If not in any group, fall through to INDIVIDUAL behavior below.

        # INDIVIDUAL or fallback
        v_min, v_max = _safe_min_max(series)
        normalized = (series - v_min) / float(v_max - v_min)
        normalized_cols[ch] = pd.Series(normalized, index=channel_df.index)

    return pd.DataFrame(normalized_cols, index=channel_df.index)



class ChannelNormalizationModeNormalizingMixin:
    """Reusable normalization mixin for detail renderers.

    Stores common normalization configuration and provides a helper to compute
    per-channel normalized data (and its global y-range) either over the full
    reference dataset or only over the current detail window.

    Expected usage (inside a renderer):

        class MyRenderer(ChannelNormalizationModeNormalizingMixin):
            def __init__(self, channel_names: Sequence[str], **kwargs):
                ChannelNormalizationModeNormalizingMixin.__init__(
                    self,
                    channel_names=channel_names,
                    fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE,
                    normalization_mode_dict=...,
                    arbitrary_bounds=...,
                    normalize=True,
                    normalize_over_full_data=True,
                    normalization_reference_df=full_df,
                )
                # plus your own init...

            def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: pd.DataFrame):
                channel_names = self.channel_names
                norm_df, (y_min, y_max) = self.compute_normalized_channels(
                    detail_df=detail_data,
                    channel_names=channel_names,
                )
                # use norm_df.loc[detail_df.index] for plotting, then:
                # if np.isfinite(y_min) and np.isfinite(y_max) and y_max > y_min:
                #     plot_item.setYRange(y_min, y_max, padding=0.05)
    """
    @property
    def visible_channel_names(self) -> List[str]:
        """The visible_channel_names computed from self._channel_visibility_state and self.channel_names."""
        return [k for k in self.channel_names if self.channel_visibility.get(k, False)]


    def __init__(self, channel_names: Sequence[str],
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Mapping[Iterable[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None, initial_visibility: Optional[Dict[str, bool]] = None,
                 **kwargs):
        """Initialize normalization configuration for a renderer-like class."""
        # Allow cooperative multiple inheritance
        super().__init__(**kwargs)

        # Initialize visibility state (all visible by default)
        if initial_visibility is None:
            self.channel_visibility = {channel: True for channel in channel_names}
        else:
            self.channel_visibility = initial_visibility.copy()
            # Ensure all channels are in the dict
            for channel in channel_names:
                if channel not in self.channel_visibility:
                    self.channel_visibility[channel] = True


        self.channel_names: List[str] = list(channel_names)
        self.fallback_normalization_mode: ChannelNormalizationMode = fallback_normalization_mode
        self.normalization_mode_dict: Optional[Mapping[Iterable[str], ChannelNormalizationMode]] = normalization_mode_dict
        self.arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = arbitrary_bounds
        self.normalize: bool = bool(normalize)
        self.normalize_over_full_data: bool = bool(normalize_over_full_data)
        # If provided, this should be a DataFrame with at least the same channel columns
        # as any detail_df passed to compute_normalized_channels.
        self.normalization_reference_df: Optional[pd.DataFrame] = normalization_reference_df
        # if self.normalization_reference_df is not None:
            
        normalize_over_full_data: bool = (self.normalization_reference_df is not None)

        self.channel_label_items = [] # : List[Tuple[pg.TextItem, float]]
        self.channel_graphics_items = []
 

    def compute_normalized_channels(self, detail_df: pd.DataFrame, channel_names: Optional[Sequence[str]] = None) -> Tuple[pd.DataFrame, Tuple[float, float]]:
        """Return (normalized_df, (y_min, y_max)) for the given detail window.

        - If `self.normalize` is False, returns the raw `detail_df[channel_names]`
          (cast to float) and its y-range.
        - If `self.normalize` is True and `self.normalize_over_full_data` is True
          and `self.normalization_reference_df` is not None, normalization
          bounds are computed over the full reference DataFrame, then the
          normalized data are sliced back to the rows in `detail_df`.
        - Otherwise, normalization bounds are computed only over `detail_df`.
        """
        if detail_df is None or detail_df.empty:
            return detail_df.iloc[0:0], (0.0, 1.0)

        if channel_names is None:
            # channel_names = self.channel_names
            channel_names = self.visible_channel_names

        # Keep only channels that actually exist in the detail frame
        channel_list: List[str] = sorted([c for c in channel_names if c in detail_df.columns])
        if not channel_list:
            return detail_df.iloc[0:0], (0.0, 1.0)

        # If we are not normalizing, just return raw values and their range
        if not self.normalize:
            ## get masked `detail_df`
            detail_df.masked_df.add_masking_column(mask_col='is_valid', value_cols=channel_list)
            masked_detail_df: pd.DataFrame = detail_df.masked_df.get_masked(copy=False)

            sub_df = masked_detail_df[channel_list].astype(float)
            y_min, y_max = _safe_min_max(sub_df.values)
            return sub_df, (y_min, y_max)

        # Choose the DataFrame over which to compute normalization statistics
        if self.normalize_over_full_data and (self.normalization_reference_df is not None):
            ref_df = self.normalization_reference_df
        else:
            ref_df = detail_df

        ## get masked `ref_df`
        ref_df.masked_df.add_masking_column(mask_col='is_valid', value_cols=channel_list)
        masked_ref_df: pd.DataFrame = ref_df.masked_df.get_masked(copy=True)

        # Compute normalized values over the reference window
        normalized_ref = normalize_channels(
            df=masked_ref_df,
            channel_names=channel_list,
            default_mode=self.fallback_normalization_mode,
            normalization_mode_dict=self.normalization_mode_dict,
            arbitrary_bounds=self.arbitrary_bounds,
        )

        # Restrict to the rows that correspond to the current detail window
        # (assumes detail_df.index is aligned with ref_df / normalized_ref indexes)
        normalized_detail = normalized_ref.loc[detail_df.index.intersection(normalized_ref.index), channel_list]

        if normalized_detail.empty:
            return normalized_detail, (0.0, 1.0)

        y_min, y_max = _safe_min_max(normalized_detail.values)
        return normalized_detail, (y_min, y_max)


    def add_channel_renderables_if_needed(self, plot_item: pg.PlotItem, force_recreate: bool=False):
        """ adds the fixed channel label items and the grid for each channel


        channel_graphics_items, channel_label_items = self.add_channel_renderables_if_needed(plot_item=self.plot_item)

        """
        assert (self.channel_names is not None)
        assert (self.visible_channel_names is not None)

        active_channel_names: List[str] = self.visible_channel_names

        has_channel_items: bool = (len(self.channel_graphics_items) == len(active_channel_names))
        plot_item_has_channel_items: bool = hasattr(plot_item, '_motion_label_items') and (getattr(plot_item, '_motion_label_items', None) is not None) and (len(plot_item._motion_label_items) == len(active_channel_names))
        if has_channel_items and plot_item_has_channel_items and (not force_recreate):
            ## update existing?
            return self.channel_graphics_items, self.channel_label_items

        # self.channel_graphics_items = []
        # self.channel_label_items: List[Tuple[pg.TextItem, float]] = []
        
        # found_channel_names: List[str] = self.channel_names
        found_channel_names: List[str] = active_channel_names

        # Filter channels based on visibility if channel_visibility is set
        if hasattr(self, 'channel_visibility') and self.channel_visibility:
            found_channel_names = [ch for ch in found_channel_names if self.channel_visibility.get(ch, True)]


        nPlots: int = len(found_channel_names)
        single_channel_height: float = 1.0 / float(nPlots)
        grid_pen = pg.mkPen(color=(100, 100, 100, 120), width=1)
        vb = plot_item.getViewBox()
        

        def _update_motion_label_positions() -> None:
            left_x = vb.viewRange()[0][0]
            for label_item, y_mid in self.channel_label_items:
                label_item.setPos(left_x, y_mid)

        # Plot each channel with its distinct color, grid lines at y_min/y_mid/y_max, and track label
        for i, a_found_channel_name in enumerate(found_channel_names):
            channel_index = self.channel_names.index(a_found_channel_name) ## original channel index color
            channel_color = self.pen_colors[channel_index]
            y_lo = float(i) * single_channel_height
            y_mid = y_lo + 0.5 * single_channel_height
            y_hi = float(i + 1) * single_channel_height
            for y_pos in (y_lo, y_mid, y_hi):
                hline = pg.InfiniteLine(angle=0, movable=False, pos=y_pos, pen=grid_pen)
                hline.setZValue(-5)
                plot_item.addItem(hline, ignoreBounds=True)
                self.channel_graphics_items.append(hline)
            label_color = channel_color if self.pen_colors else 'white'
            label_item = pg.TextItem(text=a_found_channel_name, anchor=(0, 0.5), color=label_color)
            self.channel_label_items.append((label_item, y_mid))
            label_item.setZValue(10)
            plot_item.addItem(label_item)
            self.channel_graphics_items.append(label_item)

        _update_motion_label_positions()
        plot_item._motion_label_items = self.channel_label_items
        plot_item._on_update_motion_label_positions = _update_motion_label_positions
        plot_item._motion_label_conn = vb.sigRangeChanged.connect(plot_item._on_update_motion_label_positions)

        return self.channel_graphics_items, self.channel_label_items



__all__ = ['ChannelNormalizationMode', 'build_channel_mode_map', 'normalize_channels', 'ChannelNormalizationModeNormalizingMixin']


