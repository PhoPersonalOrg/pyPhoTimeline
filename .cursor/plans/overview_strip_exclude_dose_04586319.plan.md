---
name: overview strip exclude dose
overview: Add a class-level excluded-track-name set to `TimelineOverviewStrip` and filter `primary_track_names` in `rebuild`, seeded with `DOSE_CURVES_Computed`.
todos:
  - id: add-exclusion-set
    content: Add EXCLUDED_TRACK_NAMES class attribute on TimelineOverviewStrip with 'DOSE_CURVES_Computed'
    status: completed
  - id: filter-in-rebuild
    content: Filter primary_track_names against EXCLUDED_TRACK_NAMES at the top of rebuild()
    status: completed
isProject: false
---

## Context

`TimelineOverviewStrip.rebuild` in [pypho_timeline/widgets/timeline_overview_strip.py](pypho_timeline/widgets/timeline_overview_strip.py) currently renders every name in `primary_track_names`. There is no existing in-widget name-based exclusion list — type-based filtering (EEG FP/Spectrogram) happens upstream in `_is_overview_eligible_track_datasource` in [pypho_timeline/widgets/simple_timeline_widget.py](pypho_timeline/widgets/simple_timeline_widget.py). Per the request, the exclusion belongs inside the overview strip widget itself.

## Change

In [pypho_timeline/widgets/timeline_overview_strip.py](pypho_timeline/widgets/timeline_overview_strip.py):

1. Add a class-level constant on `TimelineOverviewStrip` (just after the docstring, before the signal definitions):

```python
EXCLUDED_TRACK_NAMES: frozenset[str] = frozenset({'DOSE_CURVES_Computed'})
```

2. At the top of `rebuild` (line ~127, before the `tuples: List[Any] = []` initialization), filter the input list in-place so all downstream logic (axis labels, y-range, intervals) sees only the kept names:

```python
primary_track_names = [n for n in primary_track_names if n not in self.EXCLUDED_TRACK_NAMES]
```

This keeps the change minimal, scoped to this widget, and makes future additions a single-line edit to `EXCLUDED_TRACK_NAMES`.

## Notes / non-goals

- No changes to `simple_timeline_widget.py` — its existing type-based filter remains.
- No new public API; `EXCLUDED_TRACK_NAMES` is a class attribute that can be subclassed/overridden if needed later.
- No tests added (consistent with existing widget code in this module).