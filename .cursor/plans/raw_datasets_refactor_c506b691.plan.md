---
name: raw_datasets refactor
overview: Rename `raws_dict` to `raw_datasets` with type `Optional[List[mne.io.Raw]]` on `RawProvidingTrackDatasource`, update EEG subclasses and `stream_to_datasources` call sites to pass per-track EEG raw lists instead of the full multimodal dict.
todos:
  - id: track-datasource
    content: "RawProvidingTrackDatasource: raw_datasets param, _raw_datasets, property, from_multiple_sources; clean Dict import if unused"
    status: completed
  - id: eeg-subclasses
    content: "EEGTrackDatasource + EEGSpectrogramTrackDatasource: raw_datasets typing and super/cls kwargs"
    status: completed
  - id: stream-builder
    content: "stream_to_datasources EEG branch: eeg_raw_datasets + pass raw_datasets; dedupe eeg_raw from list"
    status: completed
isProject: false
---

# Refactor `raws_dict` → `raw_datasets` (list of MNE Raws)

## Scope

- **Primary:** `[track_datasource.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\track_datasource.py)` — `RawProvidingTrackDatasource` (`__init__`, private backing field, property, `from_multiple_sources`).
- **Subclasses:** `[eeg.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py)` — `EEGTrackDatasource` and `EEGSpectrogramTrackDatasource` (`__init__`, `from_multiple_sources`, all `super().__init__` / `cls(...)` kwargs).
- **Call sites:** `[stream_to_datasources.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\stream_to_datasources.py)` — EEG branch only (`from_multiple_sources` and `EEGSpectrogramTrackDatasource(...)`).

No changes needed in PhoPyMNEHelper `xdf_files.py` (its `raws_dict` variables are `datasets_dict` / `save_post_processed_to_fif` kwargs, not timeline datasources).

## Behavioral note (intentional tightening)

Today EEG datasources receive the **entire** `lab_obj.datasets_dict` when truthy. After this change they receive only `raws_dict.get(DataModalityType.EEG.value, [])` (the same list already used for `eeg_raws[0]` / spectrogram). Code that relied on `datasource.raws_dict` holding motion/other modalities will need `lab_xdf_obj.datasets_dict` instead.

## Implementation details

### 1. `RawProvidingTrackDatasource` in `track_datasource.py`

- Replace parameter `raws_dict: Optional[Dict[str, mne.io.Raw]] = None` with `raw_datasets: Optional[List[mne.io.Raw]] = None`.
- Rename `_raws_dict` → `_raw_datasets`; assign in `__init__`.
- Replace the `raws_dict` **property** with `raw_datasets`: getter return type `Optional[List[mne.io.Raw]]`, setter accepts `Optional[List[mne.io.Raw]]` (allow `None` for symmetry with `__init__`).
- In `from_multiple_sources`, rename parameter to `raw_datasets`, forward `raw_datasets=raw_datasets` into `cls(...)`.
- Extend the class/docstring/`__init__` docstring with one line for `lab_obj` / `raw_datasets` if you touch docstrings anyway.
- `**Dict` in this file:** only used for the old `raws_dict` hints; after removal, drop `Dict` from imports if it becomes unused (the main typing import line is `Optional, Tuple, List, Any, Union` — verify `Dict` is not imported from `typing` here; if `Dict` appears nowhere else, remove it).

### 2. `eeg.py`

- Replace `raws_dict: Optional[Any] = None` with `raw_datasets: Optional[List[mne.io.Raw]] = None` on:
  - `EEGTrackDatasource.__init__`
  - `EEGTrackDatasource.from_multiple_sources`
  - `EEGSpectrogramTrackDatasource.__init__`
  - `EEGSpectrogramTrackDatasource.from_multiple_sources`
- Replace every `raws_dict=raws_dict` passed to `super()` / `cls()` with `raw_datasets=raw_datasets`.
- **Typing:** add `from __future__ import annotations` as the first line (mirrors `track_datasource.py`) and under `TYPE_CHECKING` add `import mne` so `mne.io.Raw` resolves for static checkers without a runtime `import mne` in this module (unless you prefer a top-level `import mne`).

### 3. `stream_to_datasources.py` (EEG branch ~460–491)

- Keep the local name `raws_dict = lab_obj.datasets_dict or {}` for `.get(DataModalityType.*)` lookups.
- **Before** `EEGTrackDatasource.from_multiple_sources(...)`, define e.g. `eeg_raw_datasets = raws_dict.get(DataModalityType.EEG.value, []) if raws_dict else None` (same `type: ignore` pattern as existing `.get` lines if still needed).
- Pass `raw_datasets=eeg_raw_datasets` into `from_multiple_sources` and both `EEGSpectrogramTrackDatasource(...)` constructors.
- Inside the spectrogram block, replace `eeg_raws = raws_dict.get(...)` with reuse of `eeg_raw_datasets`: `eeg_raw = eeg_raw_datasets[0] if eeg_raw_datasets else None` (avoids duplicate `.get` and stays consistent).

### 4. Out of scope / optional

- `[testing_notebook.ipynb](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\testing_notebook.ipynb)` embeds older snippets with `raws_dict` logging — update only if you want notebook cells in sync with production code.
- `[.cursor/plans/eeg_rawproviding_subclass_fab8b093.plan.md](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\.cursor\plans\eeg_rawproviding_subclass_fab8b093.plan.md)` still describes `raws_dict`; update only if you maintain that doc.

## Verification

- Run `uv run python -m compileall` on the touched package paths or project test/lint command you use.
- Grep for `raws_dict=` / `.raws_dict` under `pypho_timeline` to ensure no stale datasource API remains (motion branch and local `raws_dict` variable in `stream_to_datasources` are fine).

