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

    def __init__(self, channel_names: Sequence[str],
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE,
                 normalization_mode_dict: Optional[Mapping[Iterable[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True,
                 normalization_reference_df: Optional[pd.DataFrame] = None,
                 **kwargs):
        """Initialize normalization configuration for a renderer-like class."""
        # Allow cooperative multiple inheritance
        super().__init__(**kwargs)

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
            channel_names = self.channel_names

        # Keep only channels that actually exist in the detail frame
        channel_list: List[str] = [c for c in channel_names if c in detail_df.columns]
        if not channel_list:
            return detail_df.iloc[0:0], (0.0, 1.0)

        # If we are not normalizing, just return raw values and their range
        if not self.normalize:
            sub_df = detail_df[sorted(channel_list)].astype(float)
            y_min, y_max = _safe_min_max(sub_df.values)
            return sub_df, (y_min, y_max)

        # Choose the DataFrame over which to compute normalization statistics
        if self.normalize_over_full_data and (self.normalization_reference_df is not None):
            ref_df = self.normalization_reference_df
        else:
            ref_df = detail_df

        # Compute normalized values over the reference window
        normalized_ref = normalize_channels(
            df=ref_df,
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





__all__ = ['ChannelNormalizationMode', 'build_channel_mode_map', 'normalize_channels', 'ChannelNormalizationModeNormalizingMixin']


