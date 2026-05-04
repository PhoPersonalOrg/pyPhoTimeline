---
name: Refactor ADHD sleep intrusions
overview: "Strip [`ADHD_sleep_intrusions.py`](c%3A%5CUsers%5Cpho%5Crepos%5CEmotivEpoc%5CACTIVE_DEV%5CPhoPyMNEHelper%5Csrc%5Cphopymnehelper%5Canalysis%5Ccomputations%5Cspecific%5CADHD_sleep_intrusions.py) down to the minimum needed by the notebooks: the compute function, the DAG node, and a single timeline-plot function. Drop param fingerprinting, the `adhd_ctx`/`out` wrapper, the closure callback, the legacy/new API split, and the failing bad-channel detection that currently produces zero windows."
todos:
  - id: rewrite-core
    content: Rewrite `ADHD_sleep_intrusions.py` with the flattened compute function (with picks fallback), minimal `ThetaDeltaSleepIntrusionComputation`, and single `apply_adhd_sleep_intrusion_to_timeline` function. Inline/drop helpers.
    status: completed
  - id: cleanup-reexports
    content: Remove the dropped symbols (`THETA_DELTA_SLEEP_INTRUSION_PARAM_KEYS`, `filter_theta_delta_sleep_intrusion_params`, `theta_delta_sleep_intrusion_params_fingerprint`) from `specific/__init__.py` and `computations/__init__.py` imports and `__all__`.
    status: completed
  - id: verify
    content: Run `ReadLints` on the rewritten file and the two `__init__.py` files; confirm `eeg_registry.py` still imports cleanly.
    status: completed
isProject: false
---

## Why it doesn't work today

The notebook output (`testing_notebook.ipynb` cell exec 7) shows `n_windows: 0, n_valid_windows: 0` because in [`ADHD_sleep_intrusions.py:251-257`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\ADHD_sleep_intrusions.py):

1. `EEGComputations.time_independent_bad_channels(raw, ...)` runs `detect_bad_channels_sliding_window` which calls `set_eeg_reference('average', projection=False)` and raises `ValueError: No channels supplied to apply the reference to` (channel types on `RawArrayExtended` aren't `eeg`).
2. The next line, `mne.pick_types(raw.info, eeg=True, exclude="bads")`, returns 0 picks for the same reason → early-return empty series.

## New file shape (target ~150 lines vs 539)

Single-pass rewrite of `ADHD_sleep_intrusions.py`. Drop these symbols entirely (with re-export cleanup):

- `THETA_DELTA_SLEEP_INTRUSION_PARAM_KEYS`, `filter_theta_delta_sleep_intrusion_params`, `theta_delta_sleep_intrusion_params_fingerprint` — unused outside this module's own re-exports; default protocol JSON fingerprint is fine
- `_apply_adhd_sleep_intrusion_to_timeline_impl` — fold into the public function
- The legacy/new dual API in `apply_adhd_sleep_intrusion_to_timeline` — single signature only
- The `adhd_ctx` dict wrapper and `apply_adhd_sleep_intrusion_to_timeline_plot_callback_fn` closure inside `ThetaDeltaSleepIntrusionComputation.compute`
- Helpers: `_merge_annotations`, `_annotations_intervals_seconds`, `_window_overlaps_intervals`, `_psd_multitaper_or_welch`, `_window_hits_sample_mask` — inline or simplify
- Bad-channel detection — pick channels via `mne.pick_types` with a fallback chain, no pyprep call

### `compute_theta_delta_sleep_intrusion_series(raw_eeg, *, motion_df=None, ...)` — flattened
- Single function, signature on one line per project rule
- Pick channels: `picks = mne.pick_types(raw.info, eeg=True, exclude='bads')`; if empty, fall back to all good data channels via `mne.pick_types(raw.info, eeg=True, meg=False, ecg=False, eog=False, misc=True, exclude='bads')` and finally `np.arange(len(raw.ch_names))` minus `info['bads']`. Fixes the 0-picks bug.
- Motion masking: build motion `mne.Annotations` via `MotionData.find_high_accel_periods` only when `motion_df is not None`; reject windows that overlap any annotation whose description contains `BAD_motion` (substring match inlined, no helpers).
- Optional autoreject mask via existing `fit_autoreject_bad_sample_mask` (already in `bad_epochs.py`, leave it).
- PSD: try `mne.time_frequency.psd_array_multitaper`, fall back to `scipy.signal.welch` (inline, no separate helper).
- Returns flat dict: `times`, `theta_delta_ratio`, `session_mean_theta_delta`, `n_windows`, `n_valid_windows`, `motion_high_accel_df`, `params`. No `bad_channel_result`, no callback.

### `ThetaDeltaSleepIntrusionComputation(SpecificComputationBase)` — minimal
- Keep `computation_id="theta_delta_sleep_intrusion"`, `version="1"`, `deps=()`, `artifact_kind=ArtifactKind.stream`.
- Drop `params_fingerprint_fn` (default protocol fingerprint covers it).
- `compute(ctx, params, dep_outputs)` body becomes 3 lines: assert `ctx.raw`, pop unsupported params, return `compute_theta_delta_sleep_intrusion_series(ctx.raw, **kw)`. No `adhd_ctx`, no closure, no extras lookup.

### `apply_adhd_sleep_intrusion_to_timeline(timeline, result, *, eeg_name, eeg_ds, t0=None)` — single function
- Required kwargs `eeg_name` and `eeg_ds`; if `t0` is None or below `eeg_ds.earliest_unix_timestamp`, derive from `eeg_ds.earliest_unix_timestamp` (existing behavior).
- Computes `x_abs = t0 + result["times"]`, `y = result["theta_delta_ratio"]`.
- If `ANALYSIS_theta_delta` track exists, refresh `ratio_ds.detailed_df` and emit `source_data_changed_signal`. Otherwise build the `EEGTrackDatasource` and `add_new_embedded_pyqtgraph_render_plot_widget` exactly as today (lines 477-505) but flattened.
- Drop `draw_on_existing_track` overlay path (unused; `_adhd_theta_delta_overlay` not referenced elsewhere).

### Re-export cleanup
- [`specific/__init__.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\__init__.py) line 3: drop `THETA_DELTA_SLEEP_INTRUSION_PARAM_KEYS`, `filter_theta_delta_sleep_intrusion_params`, `theta_delta_sleep_intrusion_params_fingerprint` from the import and `__all__`.
- [`computations/__init__.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\__init__.py) line 6: same drop.
- [`eeg_registry.py:13`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\eeg_registry.py): import unchanged (just `ThetaDeltaSleepIntrusionComputation`).

## Notebook impact (NOT modifying notebooks)

Per your rule about not editing notebooks unless explicitly included: I will leave the four `testing_*.ipynb` files alone. After the refactor, the cells that do `out_adhd['apply_adhd_sleep_intrusion_to_timeline_plot_callback_fn'](timeline)` will fail with KeyError, and `adhd_ctx = _curr_compute_result.copy(); out_adhd = adhd_ctx['out']` will fail because the result is now flat. You'll need to change those cells to:

```python
result = eeg_comps_result["theta_delta_sleep_intrusion"]
print("session_mean_theta_delta", result["session_mean_theta_delta"], "valid", result["n_valid_windows"], "/", result["n_windows"])
apply_adhd_sleep_intrusion_to_timeline(timeline, result, eeg_name=eeg_name, eeg_ds=eeg_ds)
```

If you want me to update the notebooks too, say so and I'll add it to the plan.

## Validation
- `from phopymnehelper.analysis.computations.specific import compute_theta_delta_sleep_intrusion_series, ThetaDeltaSleepIntrusionComputation` still works.
- `from phopymnehelper.analysis.computations.specific.ADHD_sleep_intrusions import apply_adhd_sleep_intrusion_to_timeline` still works.
- `run_eeg_computations_graph(eeg_raw, ..., goals=("theta_delta_sleep_intrusion",))` returns a flat dict with non-zero `n_windows` for a 52.6s `RawArrayExtended` (the picks fallback solves the 0-windows bug).
- `ReadLints` clean on the rewritten file.