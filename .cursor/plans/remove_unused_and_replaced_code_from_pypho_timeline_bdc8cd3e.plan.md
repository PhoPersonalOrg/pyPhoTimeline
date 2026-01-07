---
name: Remove unused and replaced code from pypho_timeline
overview: "Remove dead code that has been replaced by newer implementations: the entire modality_datasources.py file (7 datasource classes), a commented-out function in __main__.py, unused imports, and clean up exports."
todos:
  - id: delete_modality_datasources_file
    content: Delete pypho_timeline/rendering/datasources/modality_datasources.py (entire file with 7 unused datasource classes)
    status: pending
  - id: remove_commented_function
    content: Remove commented-out main_all_eeg_modalities_from_xdf_file_example function from __main__.py (lines 115-244)
    status: pending
  - id: remove_unused_import
    content: Remove unused 'from re import S' import from __main__.py (line 24)
    status: pending
  - id: cleanup_interval_datasource_exports
    content: Remove 'IntervalsDatasourceProtocol' from __all__ in interval_datasource.py (line 50)
    status: pending
---

# Remove Unused and Replaced Code from pypho_timeline

## Overview

Remove dead code that has been replaced by newer implementations or is no longer used anywhere in the codebase. This includes entire files, commented-out functions, unused imports, and unnecessary exports.

## Dead Code Identified

### 1. Entire File: `modality_datasources.py`

**Location**: `pypho_timeline/rendering/datasources/modality_datasources.py`**Status**: All 7 datasource classes are commented out in `__init__.py` and never imported or used. They were replaced by implementations in `rendering/datasources/specific/` directory.**Classes to remove**:

- `StringDataTrackDatasource`
- `VideoMetadataTrackDatasource` (replaced by `VideoTrackDatasource` in `specific/video.py`)
- `EEGRecordingTrackDatasource` (replaced by `EEGTrackDatasource` in `specific/eeg.py`)
- `MotionRecordingTrackDatasource` (replaced by `MotionTrackDatasource` in `specific/motion.py`)
- `PhoLogTrackDatasource`
- `WhisperTrackDatasource`
- `XDFStreamTrackDatasource`

**Helper functions in file** (also unused):

- `parse_duration_to_seconds_vectorized`
- `datetime_to_timestamp`
- `ensure_utc_naive`
- `create_default_pen_brush`

**Action**: Delete the entire file `pypho_timeline/rendering/datasources/modality_datasources.py`

### 2. Commented-Out Function in `__main__.py`

**Location**: `pypho_timeline/__main__.py` lines 115-244**Function**: `main_all_eeg_modalities_from_xdf_file_example`**Status**: Entirely commented out and replaced by `main_all_modalities_from_xdf_file_example` (line 247)**Action**: Remove the commented-out function (lines 115-244)

### 3. Unused Import in `__main__.py`

**Location**: `pypho_timeline/__main__.py` line 24**Import**: `from re import S`**Status**: Imported but never used anywhere in the file**Action**: Remove the unused import

### 4. Clean Up Exports in `interval_datasource.py`

**Location**: `pypho_timeline/rendering/datasources/interval_datasource.py` line 50**Issue**: `IntervalsDatasourceProtocol` is exported in `__all__` but is only used internally as a fallback when the real `IntervalsDatasource` cannot be imported. It's never imported or used elsewhere.**Action**: Remove `'IntervalsDatasourceProtocol'` from `__all__` (keep it in the code as it's used internally, just don't export it)

## Files to Modify

### 1. Delete File

- `pypho_timeline/rendering/datasources/modality_datasources.py` (1044 lines)

### 2. `pypho_timeline/__main__.py`

- Remove line 24: `from re import S`
- Remove lines 115-244: Entire commented-out `main_all_eeg_modalities_from_xdf_file_example` function

### 3. `pypho_timeline/rendering/datasources/interval_datasource.py`

- Line 50: Update `__all__` from `['IntervalsDatasource', 'IntervalsDatasourceProtocol']` to `['IntervalsDatasource']`

## Verification

After removal, verify:

1. No imports reference `modality_datasources` (already confirmed - all commented out)
2. No code references the removed function or import
3. Tests still pass (if any exist)
4. The `specific/` directory implementations are the active ones being used

## Impact

- **Lines removed**: ~1100+ lines of dead code
- **Files deleted**: 1 entire file