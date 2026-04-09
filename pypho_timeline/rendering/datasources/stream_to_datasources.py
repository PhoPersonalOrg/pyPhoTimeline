"""
Convert pyxdf-style stream dicts into timeline interval DataFrames and TrackDatasources.

Used by TimelineBuilder when building from XDF files or pre-loaded streams.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import pyqtgraph as pg

from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, get_reference_datetime_from_xdf_header
from pypho_timeline.xdf_session_discovery import derive_reference_datetime_from_file_metadata
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource, RawProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource
from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource, EEGSpectrogramTrackDatasource, SpectrogramChannelGroupConfig, EMOTIV_EPOC_X_SPECTROGRAM_GROUPS, aligned_chronological_raws_for_intervals, compute_multiraw_spectrogram_results
from pypho_timeline.rendering.helpers import ChannelNormalizationMode
from pypho_timeline.utils.logging_util import get_rendering_logger

logger = get_rendering_logger(__name__)

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


def default_dock_named_color_scheme_key(name: str) -> str:
    """Return a ``NamedColorScheme`` member name (``blue`` | ``green`` | ``red`` | ``grey``) for dock title bar styling from ``custom_datasource_name`` prefix. Prefix order matters (first match wins)."""
    if name.startswith('EEG_Spectrogram_'):
        return 'teal'
    if name.startswith('MOTION_'):
        return 'green'
    if name.startswith('EEGQ_'):
        return 'purple'
    if name.startswith('EEG_'):
        return 'blue'
    if name.startswith('LOG_'):
        return 'black'
    if name.startswith('UNKNOWN_'):
        return 'red'
    return 'red'


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


@function_attributes(short_name=None, tags=['MAIN', 'multi_xdf_files', 'multi-streams'], input_requires=[], output_provides=[], uses=['merge_streams_by_name', 'unix_timestamp_to_datetime', 'float_to_datetime', 'datetime_to_unix_timestamp'], used_by=['TimelineBuilder'], creation_date='2026-03-02 03:00', related_items=['perform_process_single_xdf_file_all_streams'])
def perform_process_all_streams_multi_xdf(streams_list: List[List], xdf_file_paths: List[Path], file_headers: Optional[List[dict]] = None, enable_raw_xdf_processing: bool=True, spectrogram_channel_groups: Optional[List[SpectrogramChannelGroupConfig]] = EMOTIV_EPOC_X_SPECTROGRAM_GROUPS) -> Tuple[Dict, Dict]:
    """Process streams from multiple XDF files and merge streams with the same name.

    Streams with the same name across different files will be merged into a single datasource.
    Timestamps are converted to use a common reference datetime (earliest file's reference) to ensure
    proper alignment across multiple files.

    Args:
        streams_list: List of stream lists (one per XDF file), where each stream list contains
                     stream dictionaries from pyxdf
        xdf_file_paths: List of Path objects corresponding to each stream list
        file_headers: Optional list of XDF file header dictionaries (one per file)
        enable_raw_xdf_processing: If False, skips LabRecorderXDF / MNE / spectrogram work (pyxdf-only tracks).

    Returns:
        Tuple of (all_streams dict, all_streams_datasources dict) where:
        - all_streams: Dictionary mapping stream names to merged interval DataFrames
        - all_streams_datasources: Dictionary mapping stream names to merged TrackDatasource instances
    """
    from phopymnehelper.historical_data import HistoricalData
    from phopymnehelper.xdf_files import LabRecorderXDF

    lab_obj_cache_by_resolved_path: Dict[Path, Tuple[Any, Optional[dict]]] = {}


    def _subfn_process_xdf_file(xdf_path_for_raw: Path):
        """ 
            xdf_paths_for_raw = [v[1] for v in stream_file_pairs]
            raws_dict_dict = {}
            lab_obj_dict = {}
            for a_xdf_path in xdf_paths_for_raw:
                a_lab_obj, a_raws_dict = _subfn_process_xdf_file(xdf_path_for_raw=a_xdf_path)
                lab_obj_dict[a_xdf_path] = a_lap_obj
                raws_dict_dict[a_xdf_path] = a_raws_dict


        """
        a_lab_obj = None
        a_raws_dict: Optional[dict] = None
        logger.info(f'enable_raw_xdf_processing is True so this stream will be processed as MNE raw...')
        if not xdf_path_for_raw.exists():
            return a_lab_obj, a_raws_dict
        try:
            cache_key = xdf_path_for_raw.resolve()
        except OSError:
            cache_key = xdf_path_for_raw
        if cache_key in lab_obj_cache_by_resolved_path:
            cached_lab, cached_raws = lab_obj_cache_by_resolved_path[cache_key]
            logger.debug('\tcache hit for LabRecorderXDF path "%s"', xdf_path_for_raw)
            return cached_lab, cached_raws
        logger.info(f'\ttrying to load raw XDF file load for stream_name: "{stream_name}" with xdf_path: "{xdf_path_for_raw}"...')
        try:
            a_lab_obj = LabRecorderXDF.init_from_lab_recorder_xdf_file(a_xdf_file=xdf_path_for_raw, should_load_full_file_data=True)
        except ValueError as e:
            if 'datetime' in str(e).lower() or 'UTC' in str(e):
                logger.warning(f'\tSkipping raw XDF file load for "{stream_name}" with xdf_path: {xdf_path_for_raw}: LabRecorderXDF load failed (UTC/datetime issue): {e}')
            else:
                raise
        
        if a_lab_obj is not None:
            a_raws_dict = a_lab_obj.datasets_dict or {}
            logger.info(f'\traws_dict: {a_raws_dict}')

        lab_obj_cache_by_resolved_path[cache_key] = (a_lab_obj, a_raws_dict)
        return a_lab_obj, a_raws_dict

    # ==================================================================================================================================================================================================================================================================================== #
    # BEGIN FUNCTION BODY                                                                                                                                                                                                                                                                  #
    # ==================================================================================================================================================================================================================================================================================== #

    if len(streams_list) != len(xdf_file_paths):
        raise ValueError(f"streams_list length ({len(streams_list)}) must match xdf_file_paths length ({len(xdf_file_paths)})")

    # Extract reference datetimes from file headers
    file_reference_datetimes = {}

    xdf_recording_file_metadata_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=xdf_file_paths) ## this should be cheap because most will already be cached

    if file_headers is None:
        file_headers = [None] * len(xdf_file_paths)

    for file_header, file_path in zip(file_headers, xdf_file_paths):
        ref_dt = None
        if file_header is not None:
            ref_dt = get_reference_datetime_from_xdf_header(file_header)
        if ref_dt is not None:
            file_reference_datetimes[file_path] = ref_dt
        else:
            ref_dt = derive_reference_datetime_from_file_metadata(file_path=file_path, file_comparison_df=xdf_recording_file_metadata_df)

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
        all_detailed_dfs = [] ## #TODO 2026-03-02 08:56: - [ ] these detailed_dfs are being built synchronously in the following loop too, PERFORMANCE: defer this to an async call
        stream_type = None
        stream_info = None
        lab_obj_dict: Dict[str, Optional[LabRecorderXDF]] = {}


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
                timestamps = np.asarray(timestamps, dtype=float)
                if file_ref_dt is None:
                    print(f"  WARN: No reference datetime found for {file_path.name}, timestamps may be misaligned")

            timestamps = np.asarray(timestamps, dtype=float)

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

            # Create interval DataFrame __________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
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

            # Create *detailed* DataFrame if time_series exists
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


        # Build the simple intervals _________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
        # Check if we have valid intervals
        if not all_intervals_dfs:
            print(f"  No valid intervals for stream '{stream_name}'")
            continue

        # Merge intervals for display (all_streams dict)
        merged_intervals_df = pd.concat(all_intervals_dfs, ignore_index=True).sort_values('t_start')
        all_streams[stream_name] = merged_intervals_df

        has_valid_intervals = len(merged_intervals_df) > 0
        has_detailed_data = len(all_detailed_dfs) > 0

        # Merge streams into a modality-type specific datasource _____________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
        # Create merged datasource based on stream type
        datasource = None

        ## Load the XDF raw if needed
        if enable_raw_xdf_processing:
            xdf_paths_for_raw = [v[1] for v in stream_file_pairs]

            for a_xdf_path in xdf_paths_for_raw:
                lab_obj_dict[a_xdf_path.name] = None
                try:
                    a_lab_obj, _a_raws_dict = _subfn_process_xdf_file(xdf_path_for_raw=a_xdf_path)
                    lab_obj_dict[a_xdf_path.name] = a_lab_obj
                except Exception as e:
                    raise




        # ==================================================================================================================================================================================================================================================================================== #
        # Handle Each Specific Stream Modality Type                                                                                                                                                                                                                                            #
        # ==================================================================================================================================================================================================================================================================================== #
        if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
            if has_valid_intervals and has_detailed_data:
                motion_norm_dict = modality_channels_normalization_mode_dict.get('MOTION')
                datasource = MotionTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"MOTION_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE, normalization_mode_dict=motion_norm_dict, lab_obj_dict=lab_obj_dict)

                if enable_raw_xdf_processing and any(v is not None for v in lab_obj_dict.values()):
                    logger.info(f'\tMOTION Modality MNE raw processing...')
                    motion_raws = RawProvidingTrackDatasource.get_sorted_and_extracted_raws(datasource.raw_datasets_dict)
                    if len(motion_raws) > 0:
                        try:
                            from phopymnehelper.motion_data import MotionData

                            is_moving_annots, is_moving_annots_df = MotionData.find_high_accel_periods(a_ds=datasource.detailed_df, total_change_threshold=0.5, should_set_bad_period_annotations=False, minimum_bad_duration=0.050) # at least 50ms in duration to prevent tons of tiny intervals
                            datasource.set_bad_intervals(bad_intervals_df=is_moving_annots_df, emit_changed=False)

                        except Exception as spec_e:
                            logger.warning(f'\t\tFailed to create bad period moving annotations for "{stream_name}": {spec_e}')
                    else:
                        logger.warning(f'\tNo MOTION raw found in XDF for stream "{stream_name}"; skipping spectrogram')




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
                datasource = EEGTrackDatasource.from_multiple_sources(intervals_dfs=all_intervals_dfs, detailed_dfs=all_detailed_dfs, custom_datasource_name=f"EEG_{stream_name}", max_points_per_second=10.0, enable_downsampling=True, fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL, normalization_mode_dict=eeg_norm_dict, lab_obj_dict=lab_obj_dict)
                if enable_raw_xdf_processing and any(v is not None for v in lab_obj_dict.values()):
                    logger.info(f'\tEEG MNE raw processing...')
                    aligned_raws, n_aligned_raws = aligned_chronological_raws_for_intervals(datasource.intervals_df, datasource.raw_datasets_dict)
                    if n_aligned_raws > 0:
                        try:
                            from phopymnehelper.EEG_data import EEGComputations
                            bad_channels_per_row: List[List[str]] = []
                            for i in range(n_aligned_raws):
                                bad_ch_result = EEGComputations.time_independent_bad_channels(aligned_raws[i])
                                bad_channels = list(bad_ch_result.get('all_bad_channels', []) or [])
                                if len(bad_channels) > 0:
                                    logger.info(f'Bad channels detected for "{stream_name}" interval {i}: {bad_channels}')
                                bad_channels_per_row.append(bad_channels)
                            if len(datasource.intervals_df) > len(bad_channels_per_row):
                                logger.warning('EEG bad-channel masking: interval count (%s) exceeded aligned raw count (%s); padding unmatched intervals with no bad-channel mask.', len(datasource.intervals_df), len(bad_channels_per_row))
                                bad_channels_per_row.extend([[] for _ in range(len(datasource.intervals_df) - len(bad_channels_per_row))])
                            datasource.mask_bad_eeg_channels_by_interval_rows(bad_channels_per_row, datasource.intervals_df)
                            spec_results = compute_multiraw_spectrogram_results(datasource.intervals_df, datasource.raw_datasets_dict)
                            _effective_groups = spectrogram_channel_groups if spectrogram_channel_groups is None else (spectrogram_channel_groups if len(spectrogram_channel_groups) > 0 else None)
                            if _effective_groups is None:
                                spec_datasource = EEGSpectrogramTrackDatasource(intervals_df=merged_intervals_df.copy(), spectrogram_result=None, spectrogram_results=spec_results, custom_datasource_name=f"EEG_Spectrogram_{stream_name}",
                                                                                channel_group_presets=(spectrogram_channel_groups if spectrogram_channel_groups is not None and len(spectrogram_channel_groups) > 0 else None),
                                                                                lab_obj_dict=datasource.lab_obj_dict, raw_datasets_dict=datasource.raw_datasets_dict, parent=datasource)
                                all_streams_datasources[f"EEG_Spectrogram_{stream_name}"] = spec_datasource
                                all_streams[f"EEG_Spectrogram_{stream_name}"] = merged_intervals_df
                                logger.info(f'Created EEG Spectrogram datasource for "{stream_name}"')
                            else:
                                for group_cfg in _effective_groups:
                                    group_key = f"EEG_Spectrogram_{stream_name}_{group_cfg.name}"
                                    spec_datasource = EEGSpectrogramTrackDatasource(intervals_df=merged_intervals_df.copy(), spectrogram_result=None, spectrogram_results=spec_results, custom_datasource_name=group_key, group_config=group_cfg, channel_group_presets=_effective_groups, lab_obj_dict=datasource.lab_obj_dict, raw_datasets_dict=datasource.raw_datasets_dict, parent=datasource)
                                    all_streams_datasources[group_key] = spec_datasource
                                    all_streams[group_key] = merged_intervals_df
                                logger.info(f'Created {len(_effective_groups)} EEG Spectrogram group datasources for "{stream_name}"')
                        except ImportError:
                            logger.warning(f'phopymnehelper EEG/spectrogram helpers not available; skipping spectrogram for "{stream_name}"')
                        except Exception as spec_e:
                            logger.warning(f'Failed to create spectrogram for "{stream_name}": {spec_e}')
                    else:
                        logger.warning(f'No EEG raw found in XDF for stream "{stream_name}"; skipping spectrogram')


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
    'default_dock_named_color_scheme_key',
    'merge_streams_by_name',
    'perform_process_single_xdf_file_all_streams',
    'perform_process_all_streams_multi_xdf',
]
