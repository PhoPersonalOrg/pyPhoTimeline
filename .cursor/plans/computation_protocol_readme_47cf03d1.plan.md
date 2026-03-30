---
name: Computation protocol README
overview: "Expand [COMPUTATIONS_README.md](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md) with a normative \"authoring scaffold\" section: standard method names, lifecycle/event hooks, and how they relate to the existing `ComputationNode` / `GraphExecutor` implementation in [protocol.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/protocol.py) and [engine.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/engine.py)."
todos:
  - id: draft-readme-sections
    content: Add Authoring scaffold, lifecycle events (with engine caveat), compute↔run mapping, optional build_output_renders, new-computation checklist, and cross-links to protocol/engine.
    status: completed
  - id: optional-diagram
    content: Add a short mermaid diagram for compute + orchestration hooks if it improves clarity without verbosity.
    status: completed
isProject: false
---

# Computation authoring protocol in COMPUTATIONS_README

## Current state (for alignment)

- **Registry / DAG types** already live in `[protocol.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/protocol.py)`: `ArtifactKind`, `RunContext`, `SessionFingerprint`, `ComputationNode` (fields: `id`, `version`, `deps`, `kind`, `run`, optional `params_fingerprint`), `ComputationRegistry`.
- **Execution** is synchronous in `[GraphExecutor.run](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/engine.py)`: resolve cache → call `node.run(ctx, merged_params, dep_outputs)` → store result / cache. There are **no** `on_*` callbacks or signals in the engine today.
- **Concrete nodes** (e.g. `[eeg_registry.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/eeg_registry.py)`) register plain functions as `run`. **Module-level helpers** (e.g. `[ADHD_sleep_intrusions.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/ADHD_sleep_intrusions.py)`, `[EEG_Spectograms.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/specific/EEG_Spectograms.py)`) are not yet wired as `ComputationNode`s.

The README update should **define the intended mental model and naming** for authors without requiring an immediate refactor of `protocol.py` or `engine.py`, while clearly stating what is **implemented now** vs **recommended convention / future orchestration**.

## Proposed README structure (new content)

1. **Authoring scaffold (normative)**
  - **Metadata**: every registered computation has stable `id`, semver-ish `version`, `deps`, primary `ArtifactKind`, and stable parameter hashing (`params_fingerprint` or JSON-sorted default per existing `ComputationNode`).
  - `**compute` (semantic name)**: the core algorithm; maps 1:1 to the registered callable `**run`** on `ComputationNode` with signature `(ctx: RunContext, params: Mapping[str, Any], dep_outputs: Mapping[str, Any]) -> Any`. Document this alias so readers are not confused by `run` vs `compute`.
  - **Structured outputs (recommended)**: encourage returning a small dict or dataclass with explicit keys (e.g. time axis, arrays, metadata) rather than opaque blobs, especially for `stream` / `summary` kinds—without changing legacy returns.
  - `**build_output_renders` (optional)**: separate step that turns a **cached-safe** result into timeline/UI-specific constructs (datasources, figures, HTML). Not invoked by `GraphExecutor`; called from notebooks, timeline builders, or a future adapter. Keeps analysis code independent of rendering.
2. **Lifecycle / signals (contract for orchestrators)**
  Define **event names** as part of the protocol so UIs and notebooks can subscribe consistently—even if emission is manual today:
  - `on_computation_start(node_id, ctx, params_digest_or_merged)` — before work (after cache miss decision if orchestrator exposes it).
  - `on_computation_complete(node_id, result, cache_key_or_none, meta)` — after successful `run`.
  - `on_computation_failed(node_id, exc, partial_state?)` — on error.
  - Optional: `on_cache_hit(node_id, result)` vs reusing `on_computation_complete` with a flag.
   **Explicit note**: the built-in `GraphExecutor` does **not** emit these yet; orchestration layers may wrap `GraphExecutor` / `run_eeg_computations_graph` or extend the engine later to fire them. This avoids promising behavior that the code does not provide.
3. **Minimal checklist for a new computation**
  Short bullet list: implement `compute` logic → choose `ArtifactKind` → register `ComputationNode` with `run=...` → document params → (optional) add `build_output_renders` in consumer package → (optional) wire orchestration callbacks.
4. **Cross-links**
  Link to `[computations/protocol.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/protocol.py)`, `[engine.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/engine.py)`, and `[computations/](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/)` (relative paths as today).

Optional **mermaid** (small): `Register` → `GraphExecutor` → `cache lookup` → `run (compute)` → `on_computation_complete` (dashed = orchestrator responsibility).

## Out of scope (unless you ask later)

- Adding `typing.Protocol`, base classes, or executor arguments for callbacks in Python (would be a separate change set).
- Refactoring existing `eeg_registry` nodes into classes.

## Deliverable

- Single file edit: `[PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md)` — new sections as above, concise, no tables per your preferences.

