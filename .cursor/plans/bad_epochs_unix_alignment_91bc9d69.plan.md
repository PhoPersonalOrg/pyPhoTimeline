---
name: Bad epochs Unix alignment
overview: "Your compute/plot pipeline is correct except the track helper needs the same **absolute time origin** as the EEG track: pass **`time_offset=t0`** where `t0` is the Unix time corresponding to raw time 0 (same pattern as the ADHD cell’s `apply_bad_epochs_overlays_to_timeline(..., time_offset=t0)`)."
todos:
  - id: notebook-t0
    content: "In testing_notebook: compute t0 from eeg_ds.detailed_df['t'] (datetime/numeric) and call ensure_bad_epochs_interval_track(..., time_offset=t0)"
    status: pending
  - id: optional-helper
    content: (Optional) Add bad_epochs_timeline_time_offset_from_eeg_datasource in bad_epochs.py and use in notebook
    status: pending
isProject: false
---

# Align bad-epoch interval track with Unix timeline

## Why the track looks wrong today

`[ensure_bad_epochs_interval_track](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)` maps each interval as `**time_offset + a**` and `**time_offset + b**` for `(a, b)` in `bad_epoch_intervals_rel` ([lines 170–176](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)). Defaults `**time_offset=0**`, so intervals sit at 0–48 s, 54–57 s, … on the x-axis.

XDF-backed EEG tracks use `**EEGTrackDatasource.detailed_df['t']**` in **absolute** units (after notebook normalization, **Unix seconds**). So plot x for raw sample index aligned with the dataframe is `**t0 + raw.times[i]`** with `**t0 = float(eeg_df["t"].iloc[0])**` after coercing `t` to numeric (see the existing ADHD setup cell around 

```1055:1078:C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/testing_notebook.ipynb

```).

## What to do in the notebook (minimal change)

After you have `eeg_ds` and `bad_epochs`:

1. Take the same `t0` you use for overlays / raw alignment, e.g. from the EEG dataframe (match the ADHD cell: sort by `t`, coerce datetime → seconds if needed, then first value):

```python
import pandas as pd
import numpy as np

_eeg_t = eeg_ds.detailed_df.sort_values("t")["t"]
if pd.api.types.is_datetime64_any_dtype(_eeg_t):
    t0 = float(pd.to_datetime(_eeg_t, utc=True, errors="coerce").astype(np.int64).iloc[0] / 1e9)
else:
    t0 = float(pd.to_numeric(_eeg_t, errors="coerce").iloc[0])

ensure_bad_epochs_interval_track(timeline, bad_epochs, time_offset=t0)
```

1. Use the **same** `eeg_raw` time base as the graph: `run_eeg_computations_graph(eeg_raw, ...)` must be on a `Raw` whose `raw.times` are 0 … duration for that segment, with `**meas_date`** (or equivalent) consistent with `**t0**` if you rely on MNE metadata—otherwise rely on the dataframe-derived `**t0**` above, which matches what is actually plotted.

## Optional hardening (code follow-up, if you want less boilerplate)

- Add a small helper in `[bad_epochs.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)`, e.g. `**bad_epochs_timeline_time_offset_from_eeg_datasource(eeg_ds) -> float**`, implementing the same `t` coercion as the notebook, and document it next to `**ensure_bad_epochs_interval_track**`.
- Or extend `**ensure_bad_epochs_interval_track**` with an optional `**eeg_datasource=**` that computes `time_offset` when not passed (careful with typing / lazy imports).

No change to `**BadEpochsQCComputation**` is required; the graph output stays relative to the `Raw` used in the run.

## Verification

- After the fix, bad-epoch bars should line up with `**apply_bad_epochs_overlays_to_timeline(timeline, bad_epochs, time_offset=t0)**` (if you enable overlays) and with the EEG trace’s time axis.

