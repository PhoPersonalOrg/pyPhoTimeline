---
name: Bad epochs computation
overview: Add a standalone [`bad_epochs.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py) in PhoPyMNEHelper that factorizes pyprep bad-channel QC and autoreject bad-epoch timing from [`ADHD_sleep_intrusions.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/ADHD_sleep_intrusions.py), exposes a `SpecificComputationBase` + fingerprinted params, and provides a timeline helper that adds semi-opaque black vertical regions on every `EEGTrackDatasource` and `EEGSpectrogramTrackDatasource` track. Refactor ADHD to call the shared logic so behavior stays aligned.
todos:
  - id: add-bad-epochs-module
    content: Create bad_epochs.py with compute_bad_epochs_qc, param keys/fingerprint, BadEpochsQCComputation, moved _autoreject_bad_sample_mask + shared autoreject runner, and apply_bad_epochs_overlays_to_timeline (lazy pyqtgraph/pypho_timeline imports).
    status: completed
  - id: refactor-adhd
    content: Refactor ADHD_sleep_intrusions.py to use shared bad-epoch helpers from bad_epochs.py; remove duplicated autoreject/mask code; keep motion + sliding window behavior unchanged.
    status: completed
  - id: exports
    content: Update specific/__init__.py and computations/__init__.py to export the new symbols.
    status: completed
  - id: verify
    content: Run quick import/smoke or existing tests; sanity-check overlay z-order and interval merging on contiguous bad samples.
    status: completed
isProject: false
---

# Bad epochs extraction and EEG/spectrogram overlays

## Scope

- **Extract** from `[ADHD_sleep_intrusions.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/ADHD_sleep_intrusions.py)`: bad-channel step (`EEGComputations.time_independent_bad_channels`), `_autoreject_bad_sample_mask`, and the autoreject fitting/transform block (lines 155–171, 252–282, conceptually 229–231 for `copy`/`load_data`/filter before bad channels). **Do not** pull motion annotations or sliding-window θ/δ logic into `bad_epochs`.
- **New file**: `[PhoPyMNEHelper/.../specific/bad_epochs.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)` — no imports from `ADHD_sleep_intrusions` (one-way dependency: ADHD → bad_epochs).
- **“All EEG channels”**: same practical meaning as the current ADHD pipeline — after optional bandpass, run pyprep-based bad detection on the full montage (results list which channels are bad), then run autoreject on `mne.make_fixed_length_epochs(raw, ..., reject_by_annotation="omit")` using the **same** filtered `raw` with MNE bads set (so autoreject sees the standard good/bad channel layout). Return both `bad_channel_result` and epoch-level bad coverage derived from autoreject’s `reject_log.bad_epochs` (global per epoch, matching current `_autoreject_bad_sample_mask`).

## Core API in `bad_epochs.py`

1. **Helpers** (moved or thin wrappers): `_autoreject_bad_sample_mask(raw, epochs, reject_log)` → boolean sample mask aligned to `raw` (unchanged logic).
2. **Main function** e.g. `compute_bad_epochs_qc(raw, *, l_freq=1.0, h_freq=40.0, use_autoreject=True, autoreject_epoch_sec=3.0, autoreject_kwargs=None, bad_channel_kwargs=None, copy_raw=True) -> dict`
  - Mirror ADHD preprocessing **without motion**: `copy`/`load_data`, optional Nyquist clamp for `h_freq`, `raw.filter(l_freq, h_freq)`, then `bad_channel_result = EEGComputations.time_independent_bad_channels(...)`.  
  - If `use_autoreject`: same try/import/`AutoReject`/`fit`/`transform(..., return_log=True)` pattern as today; set `ar_mask` via shared helper; on failure, `ar_mask` stays `None` with warnings.  
  - **Outputs** (cache-friendly, timeline-friendly):  
    - `bad_channel_result`  
    - `bad_epoch_intervals_rel`: list of `(t_start_sec, t_end_sec)` in **seconds on the raw timeline** (`raw.times` origin), from merging contiguous `True` runs in `ar_mask` (empty list if no mask).  
    - `autoreject_sample_mask`: optional `np.ndarray` (bool) or omit if you prefer only intervals to keep payloads small.  
    - `params`: serializable dict (bandpass, autoreject flags, etc.) for debugging/notebooks.
3. `**BadEpochsQCComputation(SpecificComputationBase)`**
  - `computation_id = "bad_epochs"` (or similar), `version = "1"`, `artifact_kind = ArtifactKind.summary` (or `stream` if you later attach renders — default **summary** is appropriate for QC dicts).  
  - Param keys frozenset + `filter_`* + `*_params_fingerprint` mirroring the ADHD pattern (json fingerprint; no non-hashable blobs).
4. **Timeline overlays** (same deferred-import style as `apply_adhd_sleep_intrusion_to_timeline` at bottom of ADHD file):
  - `apply_bad_epochs_overlays_to_timeline(timeline, result, *, time_offset: float = 0.0, z_value: float = 10.0)`  
  - **Track selection**: loop `timeline.get_all_track_names()`, take `ds = timeline.track_datasources.get(name)`, include only `[EEGTrackDatasource](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)` and `[EEGSpectrogramTrackDatasource](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)` via `isinstance` (covers `EEG_`*, `EEG_Spectrogram_*`, and grouped spectrogram track names).  
  - **Geometry**: for each interval `(a, b)` in `result["bad_epoch_intervals_rel"]`, `x0 = time_offset + a`, `x1 = time_offset + b`; add `pg.LinearRegionItem` (or equivalent) with `movable=False`, brush **black at 90% opacity** e.g. `(0, 0, 0, int(round(255 * 0.9)))`, minimal or no pen; set Z value so bands draw **above** line/spectrogram content.  
  - **Stability**: store region items on `timeline` (e.g. dict keyed by track name or a single list) and **remove/replace** on repeated calls to avoid duplicates (same pattern as `timeline._adhd_theta_delta_overlay`).  
  - `**time_offset`**: same convention as ADHD (`adhd_ctx["t0"]`): raw-relative seconds shifted to the timeline x-axis (unix or session float).

## Refactor ADHD

- Import shared `_autoreject_bad_sample_mask` and optionally a small internal `_run_autoreject_mask(raw, ...)` from `bad_epochs` to remove duplication, **or** call `compute_bad_epochs_qc` with parameters subset and reuse `autoreject_sample_mask` inside `compute_theta_delta_sleep_intrusion_series` (second option avoids two bandpass passes if you add a flag like `skip_bad_channel_if_already_done` — prefer **minimal** change: move helpers + have ADHD call one shared “autoreject mask only” function if that avoids double `time_independent_bad_channels`; if a single shared `compute_bad_epochs_qc` would double bandpass cost, factor only `_autoreject_bad_sample_mask` + a private `_fit_autoreject_sample_mask(raw, ...)` used by both modules).  
- Trim moved code from ADHD; keep motion and window loop unchanged.

## Registration / exports

- `[specific/__init__.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/__init__.py)`: export new class + main compute + param helpers + overlay function names in `__all__`.  
- `[computations/__init__.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/__init__.py)`: re-export for symmetry with `ThetaDeltaSleepIntrusionComputation` (optional: add to DAG `[eeg_registry.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/eeg_registry.py)` only if you want `run_eeg_computations_graph` to run it — not required for the feature).

## Dependencies / packaging

- PhoPyMNEHelper already lists `[autoreject](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/pyproject.toml)` and `pyprep`. Timeline overlay code uses **lazy imports** of `pyqtgraph`, `pypho_timeline...eeg`, so core `compute_`* stays importable without pyPhoTimeline (same pattern as ADHD’s apply function).

## Verification

- Smoke: `compute_bad_epochs_qc` on a tiny `RawArray` with `use_autoreject=False` returns bad_channel_result and empty intervals; with `use_autoreject=True` (if epochs sufficient) returns non-empty intervals when reject_log marks bad epochs.  
- Manual/notebook: run overlay helper after building a timeline with at least one EEG and one spectrogram track; confirm vertical bands align with `time_offset` and sit on top at ~90% black.

