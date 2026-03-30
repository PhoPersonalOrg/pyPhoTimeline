---
name: ADHD computation base class
overview: |
  Introduce a `SpecificComputationBase` subclass in `ADHD_sleep_intrusions.py` that implements `compute(ctx, params, dep_outputs)` by delegating to the existing `compute_theta_delta_sleep_intrusion_series`, while preserving the public function API and hardening param handling for merged graph params.
todos:
  - id: whitelist-params
    content: Add allowed-param names + filter helper; optional params_fingerprint_fn for motion_df-safe hashing
    status: completed
  - id: subclass
    content: Implement ThetaDeltaSleepIntrusionComputation with compute() delegating to existing function
    status: completed
  - id: exports
    content: Update __all__ and specific/__init__.py (and parent __init__ if needed)
    status: completed
isProject: false
---

# Convert ADHD_sleep_intrusions to SpecificComputationBase

## Context

- `[base.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\base.py)` defines `SpecificComputationBase`: required class attrs `computation_id`, `version`; optional `deps`, `artifact_kind`, `params_fingerprint_fn`; abstract `compute(self, ctx, params, dep_outputs)`.
- `[ADHD_sleep_intrusions.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\ADHD_sleep_intrusions.py)` today exposes only `compute_theta_delta_sleep_intrusion_series(raw_eeg, motion_df=None, **kwargs)` — no graph signature.
- `[GraphExecutor](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\engine.py)` merges **global** and per-node params; keys like `nperseg` from the EEG graph would be forwarded to every node unless filtered. The new `compute` must **only pass whitelisted keys** into the existing function.

## Implementation

1. **Keep** all private helpers and `**compute_theta_delta_sleep_intrusion_series**` unchanged in behavior (same docstring, return dict, `__all_`_ still exports the function for notebooks and [specific/**init**.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific__init__.py)).
2. **Add** a frozen set (or tuple) of allowed param names matching the function’s kwargs after `motion_df`: e.g. `motion_df`, `total_accel_threshold`, `minimum_motion_bad_duration`, `meas_date`, `l_freq`, `h_freq`, `window_sec`, `step_sec`, `delta_band`, `theta_band`, `use_autoreject`, `autoreject_epoch_sec`, `autoreject_kwargs`, `bad_channel_kwargs`, `channel_agg`, `copy_raw`, `motion_description_substr`.
3. **Add** subclass, e.g. `ThetaDeltaSleepIntrusionComputation(SpecificComputationBase)`:
  - `computation_id`: stable string (e.g. `"theta_delta_sleep_intrusion"`).
  - `version`: `"1"` (semver-style for cache invalidation per README).
  - `deps`: `()` — current algorithm runs its own `time_independent_bad_channels` internally; declaring a DAG dep on `time_independent_bad_channels` would duplicate work unless the core is later refactored to consume `dep_outputs`.
  - `artifact_kind`: `ArtifactKind.stream` (time series: `times`, `theta_delta_ratio`).
  - `params_fingerprint_fn` (recommended): a small function that builds a JSON-stable fingerprint from **filtered** params only, and handles `motion_df` explicitly (e.g. omit or replace with a short placeholder so the default serializer does not stringify an entire `DataFrame` into the cache key). If omitted, default node hashing may be huge/unstable when `motion_df` is present.
4. `**compute`**: require `ctx.raw`; `motion_df = filtered.pop("motion_df", None)` (or get then remove); call `return compute_theta_delta_sleep_intrusion_series(ctx.raw, motion_df=motion_df, **filtered)`. Single-line method bodies/signatures where they fit per project style.
5. **Exports**: extend `__all__` with the new class; update [specific/**init**.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific__init__.py) to import and re-export it (and add to package `__all_`_). Optionally update [computations/**init**.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations__init__.py) if you want it at the top-level `phopymnehelper.analysis.computations` namespace—only if that file already re-exports specific symbols.
6. **Out of scope unless you ask**: registering the node in `[eeg_registry.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\eeg_registry.py)` via `ThetaDeltaSleepIntrusionComputation().to_computation_node()` — conforming the module does not require wiring into `DEFAULT_REGISTRY`.

## Docstring touch-up

- Module docstring: add one sentence that graph/DAG use should go through `ThetaDeltaSleepIntrusionComputation` and `to_computation_node()` / `run_fn()`, while direct calls keep using `compute_theta_delta_sleep_intrusion_series`.

