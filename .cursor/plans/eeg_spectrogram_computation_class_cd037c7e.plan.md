---
name: EEG spectrogram computation class
overview: Add a `SpecificComputationBase` subclass in `EEG_Spectograms.py` that wraps existing `compute_raw_eeg_spectrogram`, with stable param filtering/fingerprinting consistent with `bad_epochs.py`. Optionally wire the default EEG registry to this node so the built-in `"spectogram"` id benefits from filtered params.
todos:
  - id: implement-class
    content: Add EEGSPECTROGRAM_PARAM_KEYS, filter/fingerprint helpers, and EEGSpectrogramComputation in EEG_Spectograms.py; update __all__
    status: completed
  - id: wire-registry
    content: Replace _spectogram_run in eeg_registry.py with EEGSpectrogramComputation().to_computation_node()
    status: completed
  - id: export-specific-init
    content: "Export new symbols from specific/__init__.py (optional: computations/__init__.py)"
    status: completed
isProject: false
---

# EEG spectrogram `SpecificComputationBase` implementation

## Context

- `[EEG_Spectograms.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\EEG_Spectograms.py)` already exposes `compute_raw_eeg_spectrogram`, which delegates to `[EEGComputations.raw_spectogram_working](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\EEG_data.py)` (`picks`, `nperseg`, `noverlap`, `mask_bad_annotated_times`).
- `[BadEpochsQCComputation](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\bad_epochs.py)` is the reference pattern: `ClassVar` metadata, `filter_*_params`, `*_params_fingerprint`, `compute` requires `ctx.raw` and delegates to the module-level compute function.
- The default graph in `[eeg_registry.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\eeg_registry.py)` already registers id `**"spectogram"**` (spelling preserved), `version="1"`, `deps=("time_independent_bad_channels",)`, `ArtifactKind.stream`, calling `raw_spectogram_working` directly. Aligning the new class with these values allows a one-line registry swap and avoids duplicate node ids.

## Implementation (single file focus + small re-exports)

### 1. Extend `[EEG_Spectograms.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\EEG_Spectograms.py)`

Add:

- `**EEG_SPECTROGRAM_PARAM_KEYS**`: `frozenset({"nperseg", "noverlap", "picks", "mask_bad_annotated_times"})`.
- `**filter_eeg_spectrogram_params(params) -> dict**`: subset of `params` for those keys only (same idea as `filter_bad_epochs_qc_params`).
- `**eeg_spectrogram_params_fingerprint(params) -> str**`: `json.dumps` sorted keys, `default=str` (handles `picks` lists / mixed types safely).
- `**EEGSpectrogramComputation(SpecificComputationBase)**`:
  - `computation_id = "spectogram"` — matches existing registry id.
  - `version = "1"`.
  - `deps = ("time_independent_bad_channels",)`.
  - `artifact_kind = ArtifactKind.stream`.
  - `params_fingerprint_fn = eeg_spectrogram_params_fingerprint`.
  - `compute`: if `ctx.raw is None`, raise `ValueError`; return `compute_raw_eeg_spectrogram(ctx.raw, **filter_eeg_spectrogram_params(params))`.

Imports: `json`, typing (`Callable`, `ClassVar`, `FrozenSet`, `Mapping`, `Optional`, `Tuple`), `RunContext`, `ArtifactKind` from protocol, `SpecificComputationBase` from base. Keep two blank lines between top-level functions and between class methods per project style.

Update `__all__` to export the new public names.

### 2. Wire default EEG registry (recommended)

In `[eeg_registry.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\eeg_registry.py)`:

- Import `EEGSpectrogramComputation` from `phopymnehelper.analysis.computations.specific.EEG_Spectograms`.
- Remove `_spectogram_run` (or leave unused and delete).
- In `ensure_default_eeg_registry` and `register_eeg_computation_nodes`, register `EEGSpectrogramComputation().to_computation_node()` instead of the inline `ComputationNode` for `"spectogram"`.

This keeps a single implementation and ensures merged `global_params` from `[GraphExecutor](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\engine.py)` cannot pass stray keys into `raw_spectogram_working`.

### 3. Re-export from `[specific/__init__.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\__init__.py)`

Add imports and `__all__` entries for `EEG_SPECTROGRAM_PARAM_KEYS`, `EEGSpectrogramComputation`, `filter_eeg_spectrogram_params`, `eeg_spectrogram_params_fingerprint`.

(Optional) Add the same symbols to the package `[computations/__init__.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\__init__.py)` for parity with `BadEpochsQCComputation`; skip if you prefer minimal public API surface.

## Testing

- Quick smoke: instantiate `EEGSpectrogramComputation`, call `to_computation_node()`, assert `id == "spectogram"` and `run` is callable (or run `ensure_default_eeg_registry()` and execute graph with goals `("spectogram",)` on a tiny `Raw` if you have a local test pattern).

No changes to `COMPUTATIONS_README.md` unless you want a one-line cross-reference under “Implementations” (user did not request docs).