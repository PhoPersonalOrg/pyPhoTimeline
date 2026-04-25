---
name: dose datasource inheritance
overview: Change `DoseTrackDatasource` so it is an interval/dataframe-backed datasource rather than a raw/MNE-backed datasource, while keeping the existing dose curve behavior intact.
todos:
  - id: update-inheritance
    content: Update import, class base, docstring, constructor super call, and remove raw extraction hook.
    status: completed
  - id: verify-dose-file
    content: Check lints and run a narrow syntax/import verification if available.
    status: completed
isProject: false
---

# Dose Datasource Inheritance Plan

I’ll make a focused edit in [`pypho_timeline/rendering/datasources/specific/dose.py`](pypho_timeline/rendering/datasources/specific/dose.py):

- Replace the `RawProvidingTrackDatasource` import/inheritance with `IntervalProvidingTrackDatasource` for `DoseTrackDatasource`.
- Update the class docstring to describe dose curves as interval/dataframe-backed text-log-derived data, not LabRecorderXDF/MNE raw data.
- Remove raw-only constructor inputs from the active `DoseTrackDatasource.__init__` signature (`lab_obj_dict`, `raw_datasets_dict`) and stop passing them to `super().__init__`, since `IntervalProvidingTrackDatasource` does not accept or manage them.
- Remove the active `try_extract_raw_datasets_dict()` override, because there is no raw extraction responsibility after the base-class change.
- Clean up now-unused active imports tied only to raw/MNE access where safe, keeping the edit minimal and avoiding unrelated disabled/commented scratch code unless needed for lint/import correctness.
- Verify the edited file with lints, and if practical run a narrow import/syntax check for `pypho_timeline.rendering.datasources.specific.dose`.

Key implementation target:

```python
class DoseTrackDatasource(ComputableDatasourceMixin, IntervalProvidingTrackDatasource):
    ...
```

The existing `init_from_timeline_text_log_tracks(...)`, curve dataframe construction, detail renderer, normalization settings, and downsampling behavior should remain unchanged.