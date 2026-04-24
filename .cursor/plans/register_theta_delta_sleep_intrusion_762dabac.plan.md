---
name: Register theta_delta_sleep_intrusion
overview: Fix the KeyError by registering the existing `ThetaDeltaSleepIntrusionComputation` node in the same places as `EEGSpectrogramComputation` and `BadEpochsQCComputation`, and optionally tightening the custom-registry bootstrap so partially-filled registries pick up the new node.
todos:
  - id: import-register-default
    content: Import ThetaDeltaSleepIntrusionComputation; register in ensure_default_eeg_registry and register_eeg_computation_nodes
    status: completed
  - id: custom-registry-guard
    content: Extend run_eeg_computations_graph else-branch to register when theta_delta_sleep_intrusion is missing
    status: completed
isProject: false
---

# Register `theta_delta_sleep_intrusion` in the EEG computation graph

## Root cause

[`ThetaDeltaSleepIntrusionComputation`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\ADHD_sleep_intrusions.py) already defines `computation_id = "theta_delta_sleep_intrusion"`, `deps=()`, and `to_computation_node()` (lines 304–317). [`eeg_registry.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\eeg_registry.py) never registers it, so [`GraphExecutor.run`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\engine.py) raises `KeyError` for that goal id.

No changes are required inside [`ADHD_sleep_intrusions.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\analysis\computations\specific\ADHD_sleep_intrusions.py) for registration; only the registry module needs wiring.

## Implementation (single file: `eeg_registry.py`)

1. **Import**  
   Add:

   `from phopymnehelper.analysis.computations.specific.ADHD_sleep_intrusions import ThetaDeltaSleepIntrusionComputation`

   (Same pattern as existing imports from `specific.bad_epochs` / `specific.EEG_Spectograms`.)

2. **`ensure_default_eeg_registry()`**  
   After `BadEpochsQCComputation().to_computation_node()`, register:

   `DEFAULT_REGISTRY.register(ThetaDeltaSleepIntrusionComputation().to_computation_node())`

3. **`register_eeg_computation_nodes()`**  
   Add:

   `_register_node_if_absent(registry, ThetaDeltaSleepIntrusionComputation().to_computation_node())`

4. **Custom-registry path in `run_eeg_computations_graph`** (recommended)  
   Today, when `registry is not None`, nodes are only auto-registered if `spectogram` or `bad_epochs` is missing (lines 86–88). A registry that already has those but not `theta_delta_sleep_intrusion` would still fail. Extend the condition to also require `reg.has("theta_delta_sleep_intrusion")` before skipping `register_eeg_computation_nodes`, so `_register_node_if_absent` can add the new node without duplicating existing entries.

## Defaults and typing

- **`EEG_COMPUTATION_IDS_ORDERED`**: Do **not** append `theta_delta_sleep_intrusion` unless you explicitly want it to run on every `goals=None` / legacy-ordered run (extra cost vs. current five-node pipeline). Your notebook passes `goals=(_curr_compute_key,)`, so registry-only registration is sufficient.
- **`EEGComputationId`** in [`type_aliases.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\type_aliases.py) is already `str`; no type change required.

## Verification

After the change, the notebook pattern:

`run_eeg_computations_graph(..., goals=("theta_delta_sleep_intrusion",))`

should return a dict containing that key with the same structure as `compute_theta_delta_sleep_intrusion_series` (e.g. `times`, `theta_delta_ratio`, …). Pass `motion_df` and other kwargs via `global_params` as you do for other parameterized nodes (filtered by `THETA_DELTA_SLEEP_INTRUSION_PARAM_KEYS` inside the computation).
