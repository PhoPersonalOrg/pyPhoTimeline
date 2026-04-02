---
name: Register bad_epochs EEG node
overview: Wire `BadEpochsQCComputation` into the default EEG computation registry and ordered legacy tuple so `run_eeg_computations_graph` accepts `"bad_epochs"` as a goal, matching the existing pattern used for `EEGSpectrogramComputation`.
todos:
  - id: import-register
    content: Import BadEpochsQCComputation; register in ensure_default_eeg_registry + register_eeg_computation_nodes; extend EEG_COMPUTATION_IDS_ORDERED
    status: completed
  - id: idempotent-guard
    content: Make register_eeg_computation_nodes skip existing ids; widen run_eeg_computations_graph else-branch for bad_epochs
    status: completed
  - id: verify-smoke
    content: Smoke-test run_eeg_computations_graph with goals=("bad_epochs",) on a tiny Raw
    status: completed
isProject: false
---

# Register `bad_epochs` in EEG computation graph

## Context

- `[eeg_registry.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/eeg_registry.py)` registers four inline nodes plus `EEGSpectrogramComputation().to_computation_node()`. It does **not** register `[BadEpochsQCComputation](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)` (`computation_id="bad_epochs"`), so the executor rejects that goal (your notebook already hit `KeyError: "Unknown goal computation id: 'bad_epochs'"`).
- `[bad_epochs.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/bad_epochs.py)`: `BadEpochsQCComputation` is complete—`deps=()`, `ArtifactKind.summary`, delegates to `compute_bad_epochs_qc`. **No changes required there** unless you later want DAG reuse of `time_independent_bad_channels` output (today `compute_bad_epochs_qc` runs bad-channel detection internally again).

## Changes (PhoPyMNEHelper only)

### 1. `[eeg_registry.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/eeg_registry.py)`

- **Import** `BadEpochsQCComputation` from `phopymnehelper.analysis.computations.specific.bad_epochs` (alongside `EEG_Spectograms`).
- **Extend** `EEG_COMPUTATION_IDS_ORDERED` to include `"bad_epochs"`. Suggested order: immediately after `"time_independent_bad_channels"` so legacy ordered dict groups QC before topo/CWT/spectrogram:
  `("time_independent_bad_channels", "bad_epochs", "raw_data_topo", "cwt", "spectogram")`
- `**ensure_default_eeg_registry`**: after the existing registrations (including spectrogram), add:
  `DEFAULT_REGISTRY.register(BadEpochsQCComputation().to_computation_node())`
- `**register_eeg_computation_nodes**`: register the same node on the passed registry.

### 2. Idempotent registration + `run_eeg_computations_graph` guard (recommended)

`[ComputationRegistry.register](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/protocol.py)` raises on duplicate IDs. Today `run_eeg_computations_graph` only calls `register_eeg_computation_nodes` when `not reg.has("spectogram")`. If we only add `"or not reg.has("bad_epochs")"` without making registration conditional, a registry that already has `spectogram` would call `register_eeg_computation_nodes` and **fail** on the first duplicate.

**Minimal fix:** in `register_eeg_computation_nodes`, register each node only if `not registry.has(node.id)` (small local helper or six one-line guards). Then update the else-branch in `run_eeg_computations_graph` to:

`if not reg.has("spectogram") or not reg.has("bad_epochs"): register_eeg_computation_nodes(reg)`

This keeps custom registries upgradable when new nodes are added.

### 3. No `__init__.py` changes

`[analysis/computations/__init__.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/__init__.py)` already exports `BadEpochsQCComputation`; wiring is registry-only.

## Verification

- Smoke: `ensure_default_eeg_registry()` then `run_eeg_computations_graph(raw, session=..., goals=("bad_epochs",))` returns a dict with key `"bad_epochs"`.
- Default run without `goals` now also executes `bad_epochs` (because defaults use `EEG_COMPUTATION_IDS_ORDERED`); that **adds cost** (filter + optional autoreject). If you want it **opt-in only**, say so and we can omit `"bad_epochs"` from `EEG_COMPUTATION_IDS_ORDERED` while still registering the node for explicit `goals`.

