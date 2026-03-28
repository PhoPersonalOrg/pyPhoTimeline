---
name: Expand NamedColorScheme
overview: Extend `NamedColorScheme` and `CustomCyclicColorsDockDisplayConfig.get_colors` in `dock_display_configs.py` with six new schemes (purple, black, orange, pink, teal, white), using dim/non-dim bg/border pairs consistent with existing patterns and dark title text for the white scheme.
todos:
  - id: enum-and-branches
    content: Extend NamedColorScheme enum and add six elif branches in get_colors (with white fg override)
    status: completed
isProject: false
---

# Add NamedColorScheme members and dock colors

## File

[dock_display_configs.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/docking/dock_display_configs.py)

## Changes

1. **Enum (line ~214)**
  Replace:
   `NamedColorScheme = Enum('NamedColorScheme', 'blue green red grey')`  
   with:
   `NamedColorScheme = Enum('NamedColorScheme', 'blue green red grey purple black orange pink teal white')`  
   Functional `Enum` appends new names; existing members `blue`–`grey` keep the same string `.name` values, so `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` `NamedColorScheme[_scheme_key]` and `[stream_to_datasources.default_dock_named_color_scheme_key](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)` stay valid.
2. `**CustomCyclicColorsDockDisplayConfig.get_colors`**
  After the `grey` branch and before `else: raise NotImplementedError`, add `elif` branches for:
  - **purple** — violet tones, distinct from blue (`#552288` / `#8844cc` style dim/bright bg with darker borders).
  - **black** — near-black bg, dark border; keep default fg (`#fff` / `#aaa`) for contrast.
  - **orange** — amber/orange dim/bright pair.
  - **pink** — rose/mauve dim/bright pair.
  - **teal** — cyan-teal dim/bright pair.
  - **white** — light bg; **override `fg_color`** in this branch only (`#1a1a1a` non-dim, `#555555` dim) so text is visible on light background.

## Follow-up (optional)

- Update the docstring on `default_dock_named_color_scheme_key` to mention the extended enum if you start returning new keys from stream processing.

## Verification

- `NamedColorScheme['purple']` … `NamedColorScheme['white']` resolve.
- `CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme.teal).get_colors('horizontal', False)` returns sensible triples; white scheme returns dark fg.

