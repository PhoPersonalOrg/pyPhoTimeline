---
name: lab_obj raw_datasets to dicts
overview: Rename `lab_obj` and `raw_datasets` to `lab_obj_dict` and `raw_datasets_dict` (with Dict types) across the RawProvidingTrackDatasource class hierarchy and all call sites.
todos:
  - id: track-datasource-base
    content: "Update RawProvidingTrackDatasource in track_datasource.py: imports, __init__, properties, from_multiple_sources, ComputableDatasourceMixin docstring"
    status: completed
  - id: eeg-subclasses
    content: "Update EEGTrackDatasource and EEGSpectrogramTrackDatasource in eeg.py: __init__, super() calls, from_multiple_sources, compute() methods"
    status: completed
  - id: motion-subclass
    content: "Update MotionTrackDatasource in motion.py: __init__, super() call, from_multiple_sources"
    status: completed
  - id: video-subclass
    content: "Update VideoTrackDatasource in video.py: __init__, super() call"
    status: completed
  - id: stream-to-datasources
    content: "Update call sites in stream_to_datasources.py: MotionTrackDatasource/EEGTrackDatasource creation, spectrogram kwargs, remove unused lab_obj local"
    status: completed
  - id: timeline-builder
    content: "Update call site in timeline_builder.py: spectrogram kwargs accessing properties"
    status: completed
  - id: testing-notebook
    content: Update testing_notebook.ipynb cells accessing .raw_datasets, .lab_xdf_obj, and lab_obj/raw_datasets kwargs
    status: completed
isProject: false
---

# Refactor lab_obj / raw_datasets to Dict-based in RawProvidingTrackDatasource hierarchy

## Summary of changes

Convert single-value parameters to dict-keyed parameters across the entire `RawProvidingTrackDatasource` class hierarchy:

- `lab_obj: Optional[LabRecorderXDF] = None` --> `lab_obj_dict: Dict[str, Optional[LabRecorderXDF]] = {}`
- `raw_datasets: Optional[List[mne.io.Raw]] = None` --> `raw_datasets_dict: Dict[str, Optional[List[mne.io.Raw]]] = None`

The dict key is `str` (XDF file name or similar identifier), matching the pattern already used by `lab_obj_dict` / `raws_dict_dict` in `stream_to_datasources.py`.

---

## File 1: [track_datasource.py](pypho_timeline/rendering/datasources/track_datasource.py)

**Add `Dict` to imports** (line 15):

```python
from typing import Protocol, Optional, Tuple, List, Dict, Any, Union, runtime_checkable
```

`**RawProvidingTrackDatasource.__init__**` (lines 793-815):

- Rename params: `lab_obj` -> `lab_obj_dict` (default `{}`), `raw_datasets` -> `raw_datasets_dict` (default `None`)
- Rename storage: `self._lab_xdf_obj = lab_obj` -> `self._lab_obj_dict = lab_obj_dict if lab_obj_dict is not None else {}`
- Rename storage: `self._raw_datasets = raw_datasets` -> `self._raw_datasets_dict = raw_datasets_dict`

**Properties** (lines 818-833):

- `lab_xdf_obj` property -> rename to `lab_obj_dict`, return type `Dict[str, Optional[LabRecorderXDF]]`, getter returns `self._lab_obj_dict`
- `raw_datasets` property -> rename to `raw_datasets_dict`, return type `Optional[Dict[str, Optional[List[mne.io.Raw]]]]`, getter returns `self._raw_datasets_dict`
- Update setters similarly

`**from_multiple_sources`** (lines 836-875):

- Rename params: `lab_obj` -> `lab_obj_dict` (default `{}`), `raw_datasets` -> `raw_datasets_dict` (default `None`)
- Update `cls(...)` call: `lab_obj=lab_obj` -> `lab_obj_dict=lab_obj_dict`, `raw_datasets=raw_datasets` -> `raw_datasets_dict=raw_datasets_dict`

`**ComputableDatasourceMixin.compute` docstring** (lines 895-899): update `datasource.raw_datasets` references to `datasource.raw_datasets_dict`

---

## File 2: [eeg.py](pypho_timeline/rendering/datasources/specific/eeg.py)

`**EEGTrackDatasource.__init__`** (line 351):

- Rename params: `lab_obj` -> `lab_obj_dict` (default `{}`), `raw_datasets` -> `raw_datasets_dict` (default `None`)
- Update `super().__init__(...)` call at line 364: `lab_obj=lab_obj` -> `lab_obj_dict=lab_obj_dict`, `raw_datasets=raw_datasets` -> `raw_datasets_dict=raw_datasets_dict`

`**EEGTrackDatasource.from_multiple_sources**` (lines 438-494):

- Rename params in signature (line 440): `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `cls(...)` call (lines 492-493): `lab_obj=lab_obj` -> `lab_obj_dict=lab_obj_dict`, `raw_datasets=raw_datasets` -> `raw_datasets_dict=raw_datasets_dict`

`**EEGTrackDatasource.compute**` (lines 500-517):

- `self.raw_datasets` -> `self.raw_datasets_dict`
- `self.raw_datasets[0]` -> get first value: `list(self.raw_datasets_dict.values())[0]` (or similar flat access)
- Update parent fallback: `self.raw_datasets = self.parent().raw_datasets` -> `self.raw_datasets_dict = self.parent().raw_datasets_dict`

`**EEGSpectrogramTrackDatasource.__init__**` (line 704):

- Rename params: `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `super().__init__(...)` call at line 716

`**EEGSpectrogramTrackDatasource.from_multiple_sources**` (line 798):

- Rename params: `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `cls(...)` call at line 806

`**EEGSpectrogramTrackDatasource.compute**` (lines 813-827):

- Same pattern as `EEGTrackDatasource.compute`: `self.raw_datasets` -> `self.raw_datasets_dict`, access first value via `list(...values())[0]`

---

## File 3: [motion.py](pypho_timeline/rendering/datasources/specific/motion.py)

`**MotionTrackDatasource.__init__**` (line 366):

- Rename params: `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `super().__init__(...)` call at line 386

`**MotionTrackDatasource.from_multiple_sources**` (line 475):

- Rename params: `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `cls(...)` call (lines 525-526)

---

## File 4: [video.py](pypho_timeline/rendering/datasources/specific/video.py)

`**VideoTrackDatasource.__init__**` (line 590):

- Rename params: `lab_obj` -> `lab_obj_dict`, `raw_datasets` -> `raw_datasets_dict`
- Update `super().__init__(...)` call at line 675

---

## File 5: [stream_to_datasources.py](pypho_timeline/rendering/datasources/stream_to_datasources.py)

**Call sites for `MotionTrackDatasource.from_multiple_sources`** (lines 477-478):

- `lab_obj=lab_obj` -> `lab_obj_dict=lab_obj_dict`
- `raw_datasets=motion_raw_datasets` -> `raw_datasets_dict=` ... (build a dict keyed by xdf filename from the existing `raws_dict_dict` loop)

**Post-creation access** (lines 480-483):

- `lab_obj is not None` -> `len(lab_obj_dict) > 0` or check any values
- `motion_raw_datasets[0]` -> access first value from `raw_datasets_dict`

**Call sites for `EEGTrackDatasource.from_multiple_sources`** (lines 517-518):

- `lab_obj=lab_obj` -> `lab_obj_dict=lab_obj_dict`
- `raw_datasets=eeg_raw_datasets` -> `raw_datasets_dict=` (build dict keyed by xdf filename)

**Spectrogram kwargs** (line 541):

- `datasource.lab_xdf_obj` -> `datasource.lab_obj_dict`
- `datasource.raw_datasets` -> `datasource.raw_datasets_dict`

**Remove now-unused** `lab_obj: Optional[LabRecorderXDF] = None` local variable (line 447).

---

## File 6: [timeline_builder.py](pypho_timeline/rendering/datasources/../../timeline_builder.py)

**Spectrogram kwargs** (line 1205):

- `eeg_datasource.lab_xdf_obj` -> `eeg_datasource.lab_obj_dict`
- `eeg_datasource.raw_datasets` -> `eeg_datasource.raw_datasets_dict`

---

## File 7: [testing_notebook.ipynb](testing_notebook.ipynb)

Update notebook cells that access:

- `eeg_ds.raw_datasets` -> `eeg_ds.raw_datasets_dict`
- `eeg_ds.raw_datasets[0]` -> `list(eeg_ds.raw_datasets_dict.values())[0]`
- `eeg_ds.lab_xdf_obj` -> `eeg_ds.lab_obj_dict`
- `spec_ds.raw_datasets` -> `spec_ds.raw_datasets_dict`
- `lab_obj=...` kwarg -> `lab_obj_dict=...`

Affected cells at approximately notebook lines: 825-826, 881-882, 916, 931-935, 1393, 1431.