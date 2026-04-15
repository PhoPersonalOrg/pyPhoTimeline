---
name: Finish EDF Export Cell
overview: Complete the incomplete notebook code cell so each loaded EEG raw session from the datasource exports to an EDF file with deterministic naming and a concrete output directory.
todos:
  - id: inspect_cell
    content: Locate and minimally replace the incomplete EDF export cell body in the notebook.
    status: completed
  - id: implement_export_loop
    content: Add output directory creation, filename selection, and `save_to_edf` call for each raw.
    status: completed
  - id: verify_execution
    content: Execute/validate the notebook cell and confirm exported EDF paths are produced.
    status: completed
isProject: false
---

# Finish EDF export from EEG datasource

## Goal
Complete the unfinished notebook cell in [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\testing_notebook.ipynb](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\testing_notebook.ipynb) so `eeg_ds.raw_datasets_dict` sessions are exported to `.edf` files via the existing `save_to_edf` API.

## Planned changes
- Update the selected export cell to:
  - Build `flat_raws` from `eeg_ds._flatten_raw_lists_from_dict(eeg_ds.raw_datasets_dict)`.
  - Create an export directory (default: `sso.eeg_analyzed_parent_export_path / "exported_EDF"`).
  - Loop over raws and compute per-raw output filename.
  - Call `a_raw.save_to_edf(output_path=curr_file_edf_path)`.
  - Collect exported paths in a list and print a short summary.
- Use robust filename fallback logic:
  - Prefer source stem from `a_raw.info.get("description")` when present.
  - Fall back to `a_raw.filenames[0]` stem when available.
  - Final fallback: index-based name like `session_000.edf`.
- Keep edits minimal and localized to the existing notebook export cell (no API changes in package code).

## Validation
- Run the updated cell and verify no syntax errors.
- Confirm one EDF file per raw in `flat_raws` is written.
- Spot-check 1-2 files by reopening via MNE to confirm readable EDF output.