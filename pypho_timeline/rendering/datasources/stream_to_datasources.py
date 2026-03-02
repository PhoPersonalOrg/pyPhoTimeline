"""
Convert pyxdf-style stream dicts into timeline interval DataFrames and TrackDatasources.

Used by TimelineBuilder when building from XDF files or pre-loaded streams.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pyqtgraph as pg

from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, unix_timestamp_to_datetime, get_reference_datetime_from_xdf_header
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource
from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource
from pypho_timeline.rendering.helpers import ChannelNormalizationMode

try:
    from pyphocorehelpers.function_helpers import function_attributes
except ImportError:
    def function_attributes(**kwargs):
        return lambda f: f


modality_channels_dict = {'EEG': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
                        'MOTION': ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'],
                        'GENERIC': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
                        'LOG': ['msg'],
}

modality_sfreq_dict = {'EEG': 128, 'MOTION': 16,
                        'GENERIC': 128, 'LOG': -1,
}

## Default modality normalization modes:
modality_channels_normalization_mode_dict = {
    'EEG': {
        ('AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'): ChannelNormalizationMode.INDIVIDUAL,
    },
    'MOTION': {
        ('AccX', 'AccY', 'AccZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
        ('GyroX', 'GyroY', 'GyroZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
    },
    'GENERIC': {
        ('AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'): ChannelNormalizationMode.GROUPMINMAXRANGE,
    },
    'LOG': {
        ('msg',): ChannelNormalizationMode.NONE,
    },
}


@function_attributes(short_name=None, tags=['OLDER', 'single_xdf_file', 'multi-streams'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2026-03-02 03:06', related_items=['perform_process_all_streams_multi_xdf'])
def perform_process_single_xdf_file_all_streams(streams):
    """ previous main function, and still used for a *single* XDF file with multiple streams - processes streams to build datasources, and thus tracks.

    NOTE: for *multiple* XDF files with multiple streams each, use `perform_process_all_streams_multi_xdf`

    """
    all_streams = {}
    all_streams_datasources = {}
    for i, s in enumerate(streams):
        stream_name = s['info']['name'][0]
        stream_type = s['info']['type'][0]
        timestamps = s['time_stamps'] ## get stream data
        time_series = s['time_series'] ## get stream data

        n_channels: int = int(s['info']['channel_count'][0])
        print(f"Stream {i}: {stream_name}, channels: {n_channels}, samples: {len(timestamps)}")

        # Create a single interval representing the entire stream recording
        if len(timestamps) == 0:
            continue

        stream_start = float(timestamps[0])
        stream_end = float(timestamps[-1])
        stream_duration = stream_end - stream_start
        if stream_duration <= 0 and len(timestamps) > 1:
            ts_arr = np.asarray(timestamps, dtype=float)
            diffs = np.diff(ts_arr)
            median_dt = float(np.median(diffs)) if len(diffs) > 0 else 0.0
            if median_dt > 0:
                stream_duration = median_dt * (len(ts_arr) - 1)
            else:
                try:
                    nominal_srate = float(s['info'].get('nominal_srate', [[128.0]])[0][0])
                    stream_duration = (len(ts_arr) - 1) / max(nominal_srate, 1.0)
                except (TypeError, KeyError, IndexError, ValueError):
                    stream_duration = 1.0
            stream_end = stream_start + stream_duration

        # Create interval DataFrame with proper structure
        intervals_df = pd.DataFrame({
            't_start': [stream_start],
            't_duration': [stream_duration],
            't_end': [stream_end]
        })

        # Add visualization columns
        intervals_df['series_vertical_offset'] = (1.0) * float(i)
        intervals_df['series_height'] = 0.9

        # Create pens and brushes
        color = pg.mkColor('grey')
        color.setAlphaF(0.7)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        intervals_df['pen'] = [pen]
        intervals_df['brush'] = [brush]


        all_streams[stream_name] = intervals_df
        has_valid_intervals: bool = (intervals_df is not None) and (len(intervals_df) > 0)

        # Create datasource
        if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
            assert has_valid_intervals
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=modality_channels_dict['MOTION'])
            time_series_df['t'] = timestamps
            motion_norm_dict = modality_channels_normalization_mode_dict.get('MOTION')
            datasource = MotionTrackDatasource(motion_df=time_series_df, intervals_df=intervals_df, custom_datasource_name=f"MOTION_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict=motion_norm_dict)
            datasource.custom_datasource_name = f"MOTION_{stream_name}"

        elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name):
            assert has_valid_intervals
            from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer
            channel_names = modality_channels_dict['EEG']
            eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
            a_detail_renderer: DataframePlotDetailRenderer = DataframePlotDetailRenderer(channel_names=channel_names, fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict=eeg_norm_dict)
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=channel_names)
            time_series_df['t'] = timestamps
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=time_series_df, custom_datasource_name=f"EEGQ_{stream_name}", detail_renderer=a_detail_renderer, max_points_per_second=2.0, enable_downsampling=True)

        elif (stream_type.upper() == 'EEG'):
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=modality_channels_dict['EEG'])
            time_series_df['t'] = timestamps
            eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
            datasource = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=time_series_df, custom_datasource_name=f"EEG_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict=eeg_norm_dict)

        elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']):
            assert has_valid_intervals
            from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
            channel_names = modality_channels_dict['LOG']
            a_detail_renderer: LogTextDataFramePlotDetailRenderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10, channel_names=channel_names)
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=channel_names)
            time_series_df['t'] = timestamps
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=time_series_df, custom_datasource_name=f"LOG_{stream_name}", detail_renderer=a_detail_renderer, enable_downsampling=False)


        elif has_valid_intervals:
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=None, custom_datasource_name=f"UNKNOWN_{stream_name}", max_points_per_second=1.0, enable_downsampling=False)
            datasource.custom_datasource_name = f"UNKNOWN_{stream_name}"
            print(f'WARN: unspecific stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        else:
            datasource = None
            print(f'WARN: NO intervals_df!! unknown stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        all_streams_datasources[stream_name] = datasource
    ## END for i, s in enumerate(streams)...

    return all_streams, all_streams_datasources


def merge_streams_by_name(streams_by_file: List[Tuple[List, Path]]) -> Dict[str, List[Tuple[Dict, Path]]]:
    """Group streams by name across multiple XDF files.

    Args:
        streams_by_file: List of tuples (streams_list, file_path) where streams_list is a list of stream dictionaries
                         from pyxdf and file_path is the Path to the XDF file

    Returns:
        Dictionary mapping stream names to lists of (stream_dict, file_path) tuples
    """
    streams_by_name = {}
    for streams, file_path in streams_by_file:
        for stream in streams:
            stream_name = stream['info']['name'][0]
            if stream_name not in streams_by_name:
                streams_by_name[stream_name] = []
            streams_by_name[stream_name].append((stream, file_path))
    return streams_by_name


@function_attributes(short_name=None, tags=['MAIN', 'multi_xdf_files', 'multi-streams'], input_requires=[], output_provides=[], uses=[], used_by=['TimelineBuilder'], creation_date='2026-03-02 03:00', related_items=['perform_process_single_xdf_file_all_streams'])
def perform_process_all_streams_multi_xdf(streams_list: List[List], xdf_file_paths: List[Path], file_headers: Optional[List[dict]] = None) -> Tuple[Dict, Dict]:
    """Process streams from multiple XDF files and merge streams with the same name.

    Streams with the same name across different files will be merged into a single datasource.
    Timestamps are converted to use a common reference datetime (earliest file's reference) to ensure
    proper alignment across multiple files.

    Args:
        streams_list: List of stream lists (one per XDF file), where each stream list contains
                     stream dictionaries from pyxdf
        xdf_file_paths: List of Path objects corresponding to each stream list
        file_headers: Optional list of XDF file header dictionaries (one per file)

    Returns:
        Tuple of (all_streams dict, all_streams_datasources dict) where:
        - all_streams: Dictionary mapping stream names to merged interval DataFrames
        - all_streams_datasources: Dictionary mapping stream names to merged TrackDatasource instances
    """
    from phopymnehelper.historical_data import HistoricalData

    if len(streams_list) != len(xdf_file_paths):
        raise ValueError(f"streams_list length ({len(streams_list)}) must match xdf_file_paths length ({len(xdf_file_paths)})")

    # Extract reference datetimes from file headers
    file_reference_datetimes = {}

    xdf_recording_file_metadta_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=xdf_file_paths) ## this should be cheap because most will already be cached

    if file_headers is None:
        file_headers = [None] * len(xdf_file_paths)

    for file_header, file_path in zip(file_headers, xdf_file_paths):
        ref_dt = None
        if file_header is not None:
            ref_dt = get_reference_datetime_from_xdf_header(file_header)
        if ref_dt is not None:
            file_reference_datetimes[file_path] = ref_dt
        else:
            found_file_df_matches = xdf_recording_file_metadta_df[xdf_recording_file_metadta_df['src_file'].apply(lambda s: Path(s).resolve()) == Path(file_path).resolve()]
            if len(found_file_df_matches) == 1:
                meas_datetime = found_file_df_matches.iloc[0]['meas_datetime'] if not found_file_df_matches.empty else None
                ref_dt = meas_datetime
            else:
                print(f'WARN: failed to find xdf file metadata for file file_path: "{file_path.as_posix()}" in xdf_recording_file_metadta_df: {xdf_recording_file_metadta_df}\n\tfound_file_df_matches: {found_file_df_matches}')

        if ref_dt is not None:
            file_reference_datetimes[file_path] = ref_dt
    ## END for file_header, file_path in zip(file_headers, xdf_file_paths):...

    # Find earliest reference datetime (common reference for all timestamps)
    earliest_reference_datetime = None
    if file_reference_datetimes:
        earliest_reference_datetime = min(file_reference_datetimes.values())
        print(f"Using earliest reference datetime: {earliest_reference_datetime} for timestamp normalization")

    # Group streams by name across all files
    streams_by_file = list(zip(streams_list, xdf_file_paths))
    streams_by_name = merge_streams_by_name(streams_by_file)

    all_streams = {}
    all_streams_datasources = {}

    # Process each unique stream name
    for stream_name, stream_file_pairs in streams_by_name.items():
        print(f"\nProcessing stream '{stream_name}' from {len(stream_file_pairs)} file(s)...")

        # Collect intervals and detailed data from all files for this stream name
        all_intervals_dfs = []
        all_detailed_dfs = []
        stream_type = None
        stream_info = None

        for stream, file_path in stream_file_pairs:
            current_stream_type = stream['info']['type'][0]
            if stream_type is None:
                stream_type = current_stream_type
                stream_info = stream['info']
            elif stream_type != current_stream_type:
                print(f"WARN: Stream '{stream_name}' has different types across files: {stream_type} vs {current_stream_type}")

            timestamps = stream['time_stamps']
            time_series = stream['time_series']

            if len(timestamps) == 0:
                print(f"  Skipping empty stream from {file_path.name}")
                continue

            # Convert timestamps: from relative (to file's reference) to absolute, then to relative (to earliest reference)
            file_ref_dt = file_reference_datetimes.get(file_path)
            if (file_ref_dt is not None) and (timestamps is not None):
                timestamps_absolute = float_to_datetime(timestamps, file_ref_dt)
                timestamps = datetime_to_unix_timestamp(timestamps_absolute)
            else:
                timestamps = np.array([float(ts) for ts in timestamps])
                if file_ref_dt is None:
                    print(f"  WARN: No reference datetime found for {file_path.name}, timestamps may be misaligned")

            stream_start = float(timestamps[0])
            stream_end = float(timestamps[-1])
            stream_duration = stream_end - stream_start
            if stream_duration <= 0 and len(timestamps) > 1:
                ts_arr = np.asarray(timestamps, dtype=float)
                diffs = np.diff(ts_arr)
                median_dt = float(np.median(diffs)) if len(diffs) > 0 else 0.0
                if median_dt > 0:
                    stream_duration = median_dt * (len(ts_arr) - 1)
                else:
                    try:
                        nominal_srate = float(stream['info'].get('nominal_srate', [[128.0]])[0][0])
                        stream_duration = (len(ts_arr) - 1) / max(nominal_srate, 1.0)
                    except (TypeError, KeyError, IndexError, ValueError):
                        stream_duration = 1.0
                stream_end = stream_start + stream_duration

            timestamps = unix_timestamp_to_datetime(timestamps)

            ts_index = pd.to_datetime(timestamps)
            ts_index = ts_index.tz_localize('UTC') if ts_index.tz is None else ts_index.tz_convert('UTC')
            timestamps = ts_index.values

            # Create interval DataFrame
            intervals_df = pd.DataFrame({
                't_start': [stream_start],
                't_duration': [stream_duration],
                't_end': [stream_end]
            })

            # Add visualization columns
            intervals_df['series_vertical_offset'] = 0.0
            intervals_df['series_height'] = 0.9

            # Create pens and brushes
            color = pg.mkColor('blue')
            color.setAlphaF(0.3)
            pen = pg.mkPen(color, width=1)
            brush = pg.mkBrush(color)
            intervals_df['pen'] = [pen]
            intervals_df['brush'] = [brush]

            all_intervals_dfs.append(intervals_df)

            # Create detailed DataFrame if time_series exists
            if time_series is not None and len(time_series) > 0:
                n_channels = int(stream['info']['channel_count'][0])
                n_t_stamps, n_columns = np.shape(time_series)

                if n_channels == n_columns and len(timestamps) == n_t_stamps:
                    if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
                        channel_names = modality_channels_dict['MOTION']
                    elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name):
                        channel_names = modality_channels_dict['EEG']
                    elif (stream_type.upper() == 'EEG'):
                        channel_names = modality_channels_dict['EEG']
                    elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']):
                        channel_names = modality_channels_dict['LOG']
                    else:
                        channel_names = [f'Channel_{i}' for i in range(n_columns)]

                    time_series_df = pd.DataFrame(time_series, columns=channel_names)
                    time_series_df['t'] = timestamps
                    all_detailed_dfs.append(time_series_df)
        ## END for stream, file_path in stream_file_pairs

        # Check if we have valid intervals
        if not all_intervals_dfs:
            print(f"  No valid intervals for stream '{stream_name}'")
            continue

        # Merge intervals for display (all_streams dict)
        merged_intervals_df = pd.concat(all_intervals_dfs, ignore_index=True).sort_values('t_start')
        all_streams[stream_name] = merged_intervals_df

        has_valid_intervals = len(merged_intervals_df) > 0
        has_detailed_data = len(all_detailed_dfs) > 0

        # Create merged datasource based on stream type
        datasource = None

        if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
            if has_valid_intervals and has_detailed_data:
                motion_norm_dict = modality_channels_normalization_mode_dict.get('MOTION')
                datasource = MotionTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"MOTION_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict=motion_norm_dict)

        elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name):
            if has_valid_intervals and has_detailed_data:
                from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer
                channel_names = modality_channels_dict['EEG']
                eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
                a_detail_renderer = DataframePlotDetailRenderer(channel_names=channel_names, fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict=eeg_norm_dict)
                datasource = IntervalProvidingTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"EEGQ_{stream_name}", detail_renderer=a_detail_renderer, max_points_per_second=2.0, enable_downsampling=True)

        elif (stream_type.upper() == 'EEG'):
            if has_valid_intervals and has_detailed_data:
                eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
                datasource = EEGTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"EEG_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict=eeg_norm_dict)

        elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']):
            if has_valid_intervals and has_detailed_data:
                from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
                channel_names = modality_channels_dict['LOG']
                a_detail_renderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10, channel_names=channel_names)
                datasource = IntervalProvidingTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"LOG_{stream_name}", detail_renderer=a_detail_renderer, enable_downsampling=False)

        elif has_valid_intervals:
            datasource = IntervalProvidingTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs if has_detailed_data else None, custom_datasource_name=f"UNKNOWN_{stream_name}", max_points_per_second=1.0, enable_downsampling=False)
            print(f'WARN: unspecific stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        all_streams_datasources[stream_name] = datasource
    ## END for stream_name, stream_file_pairs in streams_by_name.items()

    return all_streams, all_streams_datasources


__all__ = [
    'modality_channels_dict',
    'modality_sfreq_dict',
    'modality_channels_normalization_mode_dict',
    'merge_streams_by_name',
    'perform_process_single_xdf_file_all_streams',
    'perform_process_all_streams_multi_xdf',
]
