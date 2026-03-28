---
name: Modality dock colors
overview: Centralize a prefix-to-color-scheme mapping in `stream_to_datasources.py` (aligned with existing `MOTION_` / `EEG_` / `LOG_` / `EEG_Spectrogram_` naming), then use it in `timeline_builder._add_tracks_to_timeline` so every track dock gets a `CustomCyclicColorsDockDisplayConfig` with the right `NamedColorScheme` instead of the current implicit red `FigureWidgetDockDisplayConfig`.
todos:
  - id: add-scheme-helper
    content: Add default_dock_named_color_scheme_key(name) + __all__ export in stream_to_datasources.py
    status: completed
  - id: wire-timeline-builder
    content: Use helper + CustomCyclicColorsDockDisplayConfig in _add_tracks_to_timeline; keep LOG custom_button_configs
    status: completed
isProject: false
---

# Modality-based default dock colors

## Context

- In `[stream_to_datasources.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)`, **pen/brush** on interval rows are set (`grey` in single-XDF path, `blue` in multi-XDF). That affects **overview rectangles**, not dock chrome.
- **Dock title bar colors** come from `[specific_dock_widget_mixin.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/docking/specific_dock_widget_mixin.py)`: when `display_config is None`, it uses `**FigureWidgetDockDisplayConfig`** (always **red**).
- `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` `_add_tracks_to_timeline` only passes a non-`None` config for **LOG** tracks (same red `FigureWidgetDockDisplayConfig` plus the table button). All other tracks rely on that mixin default.

So changing “default dock color by modality” **requires** updating `_add_tracks_to_timeline` (or the mixin default). Your mapping can still live in `stream_to_datasources.py` as the single source of truth tied to the prefixes already assigned to `custom_datasource_name` there.

## Implementation

### 1. `[stream_to_datasources.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)`

- Add a small public helper, e.g. `default_dock_named_color_scheme_key(name: str) -> str`, that returns one of `'blue' | 'green' | 'red' | 'grey'` (the member names of `[NamedColorScheme](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/docking/dock_display_configs.py)` in `dock_display_configs.py`).
- **Prefix order matters** (first match wins). Suggested logic aligned with current naming:
  - `EEG_Spectrogram_` → `'blue'` (EEG-derived)
  - `MOTION_` → `'green'`
  - `EEGQ_` → `'blue'`
  - `EEG_` → `'blue'`
  - `LOG_` → `'grey'`
  - `UNKNOWN_` → `'red'` (or `'grey'` if you prefer low-attention unknowns)
  - **fallback** → `'red'` (same “attention” default as today’s red figure dock)
- **Do not** import `NamedColorScheme` here (keeps datasource module free of docking imports): return the string key only.
- Export the helper in `__all__`.

### 2. `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` (`_add_tracks_to_timeline`)

- Import `CustomCyclicColorsDockDisplayConfig` and `NamedColorScheme` from `dock_display_configs`, and the new helper from `stream_to_datasources`.
- For **every** track, build:
`display_config = CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme[default_dock_named_color_scheme_key(datasource.custom_datasource_name)], showCloseButton=True, showCollapseButton=False, showGroupButton=False)`  
(Omit `showTimelineSyncModeButton` unless you want to differ from current `FigureWidgetDockDisplayConfig` behavior; default on the base config is already `True`.)
- Preserve LOG-specific behavior: when `custom_datasource_name.startswith('LOG_')` and `detailed_df` is present, still `setattr(display_config, 'custom_button_configs', {...})` and keep the existing `sigCustomButtonClicked` wiring.
- Optionally set `corner_radius='3px'` on the config to match `FigureWidgetDockDisplayConfig`’s post-init (`fontSize` already defaults to `10px` on the base embed config).

### 3. No change required in `stream_to_datasources` pen/brush blocks **for dock behavior**

- If you later want **overview interval colors** to match dock hues, you can reuse the same modality inference and map to `pg.mkColor(...)` — optional, separate from dock chrome.

## Files touched


| File                                                                                                                                               | Change                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `[stream_to_datasources.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)` | New `default_dock_named_color_scheme_key`, export                                            |
| `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)`                                 | Always pass modality-based `CustomCyclicColorsDockDisplayConfig`; LOG table button unchanged |


## Verification

- Load a multi-stream XDF via the usual builder path: MOTION / EEG / LOG / spectrogram tracks should show **green / blue / grey / blue** title bars (per mapping above), not uniform red.
- LOG “show table” button still appears and works.

