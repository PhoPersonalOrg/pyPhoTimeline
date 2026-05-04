---
name: Robust empty EEG picks
overview: Handle the case where all EEG channels are excluded (bad-marked or absent) so spectrogram (and similarly CWT) computations return `None` instead of raising MNE `ValueError` from `get_data` with empty picks. No pyPhoTimeline changes required if PhoPyMNEHelper returns `None`.
todos:
  - id: guard-spectrogram
    content: Add empty-picks early return + warning in EEGComputations.raw_spectogram_working (EEG_data.py)
    status: completed
  - id: guard-cwt
    content: Add empty-picks early return + warning in EEGComputations.raw_morlet_cwt (EEG_data.py)
    status: completed
  - id: types-docs
    content: Update compute_raw_eeg_spectrogram Optional return type and docstring (EEG_Spectograms.py)
    status: completed
  - id: verify
    content: "Smoke test: graph with all-bad EEG channels returns spectogram=None without raising"
    status: completed
isProject: false
---

# Robust EEG computations when picks are empty

## Cause

In [`EEGComputations.raw_spectogram_working`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\EEG_data.py), picks are built as either `mne.pick_types(..., eeg=True, exclude='bads')` or by filtering an explicit pick list against `raw.info['bads']`. If every channel is bad or there are no EEG channels, `picks` is empty and `raw.get_data(picks=picks, ...)` raises:

`ValueError: No appropriate channels found for the given picks (array([], dtype=int32))`.

The DAG path [`GraphExecutor._execute_one`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\engine.py) does not catch exceptions, so the whole `run_eeg_computations_graph` call fails even though sibling goals (`bad_epochs`, `time_independent_bad_channels`) do not depend on the spectrogram output.

## Downstream contract (already compatible)

- [`EEGTrackDatasource.compute`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py) only appends values when `a_specific_computed_value is not None` (lines 677–681).
- [`compute_multiraw_spectrogram_results`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py) types results as `List[Optional[Dict[str, Any]]]` and uses `.get("spectogram")` which may be `None`.
- [`EEGSpectrogramTrackDatasource`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py) already treats per-interval `None` as “no spectrogram for this raw” (`was_success = any(x is not None for x in ...)`).

Returning **`None`** from the spectrogram node is the smallest change and matches existing UI expectations.

## Implementation (PhoPyMNEHelper)

### 1. `raw_spectogram_working` — early exit when no channels

**File:** [`PhoPyMNEHelper/src/phopymnehelper/EEG_data.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\EEG_data.py)

After the existing block that sets `picks` (lines 366–371), normalize and test length before any `get_data` call:

- Coerce to a 1-D integer index array (e.g. `np.asarray(picks, dtype=int).ravel()`), or if `len(picks)==0`, branch immediately.
- If empty: emit a single `warnings.warn(..., RuntimeWarning)` explaining that no EEG channels remain after exclusions (or none present), then **`return None`**.

This avoids changing STFT logic and fixes both “all channels bad” and “no EEG in `raw`” cases.

### 2. `raw_morlet_cwt` — same guard (consistency)

**Same file:** after `picks = mne.pick_types(raw.info, eeg=True, meg=False)` (line 237), if picks are empty, **`return None`** (same warning pattern). Today this path would hit the same MNE error on `get_data`. The default timeline graph does not request `cwt`, but `run_all` / other callers benefit.

### 3. Type hints / public wrapper

**File:** [`PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/EEG_Spectograms.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\EEG_Spectograms.py)

- Update `compute_raw_eeg_spectrogram` return type to **`Optional[Dict[str, Any]]`** to reflect `None`.
- Optionally add one line to the docstring: returns `None` when no channels are available for spectrogram.

No change required to [`EEGSpectrogramComputation.compute`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\EEG_Spectograms.py) beyond what the helper returns; `SpecificComputationBase` already types `compute` as `-> Any`.

### 4. Caching

[`DiskComputationCache.put`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\cache.py) pickles arbitrary values; **`None` is cache-safe**. No engine changes needed.

## Out of scope (optional follow-up)

- **Executor-level `try/except` per node** would let arbitrary failures produce `None` and continue the graph, but dependents of a failed node would need to handle `None`. The current default EEG graph has no dependents of `spectogram`, so it would help only in a broader sense; defer unless you want global fault isolation.
- **`raw_data_topo`** uses full-channel `get_data()` without EEG-only picks, so the empty-EEG-picks failure mode does not apply the same way; no change unless you see a related crash.

## Verification

- Unit-style check: construct a small `mne.io.RawArray` with 1 EEG channel, set `raw.info['bads']` to that channel name, run `run_eeg_computations_graph(..., goals=("spectogram",))` and assert `out["spectogram"] is None` and no exception.
- Or run the notebook path that previously failed and confirm `eeg_ds.compute()` completes with an empty or partial `computed_result['spectogram']` list.
