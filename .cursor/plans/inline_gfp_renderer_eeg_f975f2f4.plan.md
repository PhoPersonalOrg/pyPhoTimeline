---
name: inline gfp renderer eeg
overview: Move `LinePowerGFPDetailRenderer` (and its module-level constants/helpers) from its standalone file into `eeg.py` directly above `EEGFPTrackDatasource`, with helpers/constants folded into the class body, then delete the now-empty file and update the lazy re-export and the test stub to match.
todos:
  - id: add-imports
    content: Add `pyqtgraph` and `phopymnehelper.analysis.computations.gfp_band_power` imports to eeg.py
    status: completed
  - id: inline-renderer
    content: Insert LinePowerGFPDetailRenderer above EEGFPTrackDatasource with constants as class attrs and `_resample_channels_uniform_grid` as a classmethod
    status: completed
  - id: update-get-detail-renderer
    content: Drop the inline `from ... import LinePowerGFPDetailRenderer` in EEGFPTrackDatasource.get_detail_renderer and refresh its docstring path reference
    status: completed
  - id: repoint-lazy-export
    content: Repoint the `LinePowerGFPDetailRenderer` lazy entry in detail_renderers/__init__.py to `pypho_timeline.rendering.datasources.specific.eeg`
    status: completed
  - id: update-test
    content: Drop the line_power_gfp_detail_renderer module stub in tests/test_eegfp_track_datasource.py and read the class off the loaded eeg module
    status: completed
  - id: delete-file
    content: Delete pypho_timeline/rendering/detail_renderers/line_power_gfp_detail_renderer.py
    status: completed
isProject: false
---

## Goal
Inline `LinePowerGFPDetailRenderer` into [`pypho_timeline/rendering/datasources/specific/eeg.py`](pypho_timeline/rendering/datasources/specific/eeg.py) just above `EEGFPTrackDatasource` (currently line 983), with the existing module-level helpers/constants moved inside the class. Remove the now-redundant standalone file and update the small handful of call sites/stubs that reference the old module path.

## Scope of references found
- Real consumer: only [`EEGFPTrackDatasource.get_detail_renderer`](pypho_timeline/rendering/datasources/specific/eeg.py) (lines 1059–1062), via a local import.
- Lazy re-export: [`pypho_timeline/rendering/detail_renderers/__init__.py`](pypho_timeline/rendering/detail_renderers/__init__.py) line 15 (so `from pypho_timeline.rendering.detail_renderers import LinePowerGFPDetailRenderer` still works).
- Test stub: [`tests/test_eegfp_track_datasource.py`](tests/test_eegfp_track_datasource.py) (lines 46–55, 74) installs a fake `pypho_timeline.rendering.detail_renderers.line_power_gfp_detail_renderer` module before loading `eeg.py`.
- Docstring reference: `EEGFPTrackDatasource` docstring at line 985.
- No `isinstance(..., LinePowerGFPDetailRenderer)` checks anywhere; `apply_line_power_gfp_options_from_datasource` and `LinePowerGFPTrackOptionsPanel` only key off the datasource type, so this rename-by-location is safe.
- `phopymnehelper.analysis.computations.gfp_band_power` is a real installed module at [`PhoPyMNEHelper/src/phopymnehelper/analysis/computations/gfp_band_power.py`](../PhoPyMNEHelper/src/phopymnehelper/analysis/computations/gfp_band_power.py); `eeg.py` already eagerly imports `phopymnehelper.analysis.computations.eeg_registry`, so adding another `phopymnehelper` import keeps the same dependency surface.

## Edits

### 1) [`pypho_timeline/rendering/datasources/specific/eeg.py`](pypho_timeline/rendering/datasources/specific/eeg.py)

Add to the existing top-of-file imports (around line 17–18, next to the other `phopymnehelper` import):

```python
import pyqtgraph as pg
from phopymnehelper.analysis.computations.gfp_band_power import (
    BAND_COLORS_RGB, STANDARD_EEG_FREQUENCY_BANDS,
    bandpass_filter_channels, baseline_rescale, bootstrap_gfp_ci,
    dataframe_to_channel_matrix, estimate_sample_rate_from_t, global_field_power,
)
```

Insert a new class definition **immediately before** `class EEGFPTrackDatasource(EEGTrackDatasource):` (line 983), under the same `# === EEGFPTrackDatasource ===` banner, with:

- Class attributes replacing the deleted module-level constants:
  - `LANE_HEIGHT = 1.0`
  - `LANE_GAP = 0.15`
  - `_DEFAULT_EEG_CHANNELS = [...]` (same 14-channel list)
  - `_MAX_GFP_RESAMPLE_POINTS = 300_000`
- The free function `_resample_channels_uniform_grid` becomes a `@classmethod` named `_resample_channels_uniform_grid(cls, t_vec, data_mat, nominal_srate, max_points=None)` (default `None` → fall back to `cls._MAX_GFP_RESAMPLE_POINTS`). Body is otherwise unchanged. `render_detail` calls it as `self._resample_channels_uniform_grid(...)`.
- `__init__`, `render_detail`, `clear_detail`, `get_detail_bounds` are copied verbatim from [`line_power_gfp_detail_renderer.py`](pypho_timeline/rendering/detail_renderers/line_power_gfp_detail_renderer.py), with `LANE_HEIGHT` / `LANE_GAP` / `_DEFAULT_EEG_CHANNELS` references rewritten as `self.LANE_HEIGHT` / `self.LANE_GAP` / `self._DEFAULT_EEG_CHANNELS` (or `cls.…` inside the classmethod). The nested `to_lane` closure in `render_detail` stays a closure.
- Class docstring kept; module path reference `:mod:`phopymnehelper.analysis.computations.gfp_band_power`` unchanged.

Update `EEGFPTrackDatasource.get_detail_renderer()` (lines 1059–1062) to drop the inline import, since the class is now in the same module:

```python
def get_detail_renderer(self):
    _extra_kw = dict(channel_names=self.channel_names) if self.channel_names is not None else {}
    return LinePowerGFPDetailRenderer(live_mode=False, filter_order=self._gfp_filter_order, n_bootstrap=self._gfp_n_bootstrap, baseline_start=self._gfp_baseline_start, baseline_end=self._gfp_baseline_end, show_confidence=self._gfp_show_confidence, line_width=self._gfp_line_width, nominal_srate=self._gfp_nominal_srate, **_extra_kw)
```

Update the `EEGFPTrackDatasource` docstring on lines 984–986: change `:class:`~pypho_timeline.rendering.detail_renderers.line_power_gfp_detail_renderer.LinePowerGFPDetailRenderer`` to `:class:`LinePowerGFPDetailRenderer`` (now defined in the same module).

### 2) [`pypho_timeline/rendering/detail_renderers/__init__.py`](pypho_timeline/rendering/detail_renderers/__init__.py)

Repoint the lazy entry so `from pypho_timeline.rendering.detail_renderers import LinePowerGFPDetailRenderer` keeps working:

```15:16:pypho_timeline/rendering/detail_renderers/__init__.py
    'LinePowerGFPDetailRenderer': 'pypho_timeline.rendering.detail_renderers.line_power_gfp_detail_renderer',
```

becomes

```python
    'LinePowerGFPDetailRenderer': 'pypho_timeline.rendering.datasources.specific.eeg',
```

### 3) [`tests/test_eegfp_track_datasource.py`](tests/test_eegfp_track_datasource.py)

The test currently registers a fake `line_power_gfp_detail_renderer` module before loading `eeg.py` so that `eeg.py`'s local import succeeds (lines 46–58). After the refactor, the renderer lives inside `eeg.py` itself, so:

- Delete the `line_power_module` stub block (lines 46–58 down to the `sys.modules[line_power_module.__name__] = line_power_module` line).
- In the test method, fetch the class from the loaded module instead of `sys.modules`:

```python
LinePowerGFPDetailRenderer = mod.LinePowerGFPDetailRenderer
```

The remaining stubs (`generic_plot_renderer`, `helpers`) are independent and stay as-is. Loading the real renderer is fine because `phopymnehelper.analysis.computations.gfp_band_power` is already a runtime dependency in this environment (the test already relies on `phopymnehelper.analysis.computations.eeg_registry` being importable).

### 4) Delete file

Delete [`pypho_timeline/rendering/detail_renderers/line_power_gfp_detail_renderer.py`](pypho_timeline/rendering/detail_renderers/line_power_gfp_detail_renderer.py).

## Behavior preserved
- Public symbol path `pypho_timeline.rendering.detail_renderers.LinePowerGFPDetailRenderer` continues to resolve via the lazy `__getattr__` in `detail_renderers/__init__.py`.
- `EEGFPTrackDatasource.get_detail_renderer()` returns the same kind of object with identical kwargs.
- All math (`_resample_channels_uniform_grid`, baseline rescale, bootstrap CI, lane layout) is unchanged — only the home of the code moves and the helpers attach to the class instead of the module.