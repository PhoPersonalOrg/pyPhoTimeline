---
name: Fill COMPUTATIONS_README
overview: Populate the empty [COMPUTATIONS_README.md](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md) with the user-provided specification for what computations can access and provide, structured as clear Markdown sections with minor copyedits (e.g. preceding, spectrogram) for readability.
todos:
  - id: draft-readme
    content: Write intro + Access / Provide sections from user spec; optional “Implementations in this package” bridge with links to EEG_data.py and analysis/computations/.
    status: completed
isProject: false
---

# Fill out `COMPUTATIONS_README.md`

## Context

- Target file: `[PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/COMPUTATIONS_README.md)` — currently empty.
- Local code today: batch-style helpers live in `[EEG_data.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/EEG_data.py)` (`EEGComputations`: spectogram, CWT, topo, etc.) and `[analysis/computations/fatigue_analysis.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/analysis/computations/fatigue_analysis.py)`. The spec you gave describes the **intended computation contract** (inputs/outputs, cache, DAG, optional renderers), which may span notebooks and timeline/stream tooling—not all pieces need to exist only inside PhoPyMNEHelper.

## Document structure (to write)

1. **Title and one short intro** — Define “computations” in this repo as analysis steps that consume session/stream data and produce artifacts (time series, summaries, objects, optional views).
2. **Computations can access** — Numbered list matching your spec:
  - One or more datastreams/datasources (e.g. EEG datasource from a session).
  - A preceding required computation (dependency in a DAG).
  - A computation cache that reuses prior results when inputs/parameters are unchanged across reruns.
3. **Computations can provide** — Numbered list:
  - New datastream/datasource: time-aligned sampled/continuous values plus metadata (example: time-binned spectrogram from a channel subset and frequency band/parameters).
  - Summary/aggregate statistics (examples: average HIGH_ACCEL event count per session; session-averaged theta/delta ratio on frontal channels).
  - Raw Python result objects for downstream computations or manual export.
  - Optional custom visualization/renderer tied to results (e.g. an EEG track that shows a specific spectrogram).
4. **Optional short subsection: “Implementations in this package”** — One tight paragraph plus bullet links to `EEGComputations` and `analysis/computations/` so readers know where to look **without** claiming cache/DAG/renderer are fully implemented here unless you want that subsection omitted to keep the README purely normative. **Recommendation:** include this 3–4 line bridge so the spec doesn’t float without anchors.

## Conventions

- Use standard spelling in prose (**preceding**, **spectrogram**) while keeping your examples faithful.
- No changes to Python files or `pyproject.toml`; **only** this Markdown file.
- Keep tone spec-like: bullet semantics, examples in parentheses where you already provided them.

## Deliverable

- Single commit-ready update to `COMPUTATIONS_README.md` (~40–80 lines), no new dependencies.

