---
name: channel-normalization-modes
overview: Introduce a reusable ChannelNormalizationMode enum and helper utilities under rendering/helpers, then integrate normalization modes from datasources through motion/EEG/dataframe detail renderers.
todos:
  - id: create-helper-module
    content: Create `rendering/helpers/normalization.py` with ChannelNormalizationMode enum, normalization helpers, and updated usage examples using tuple keys.
    status: pending
  - id: wire-generic-renderer
    content: Refactor `generic_plot_renderer.py` to import the shared ChannelNormalizationMode, remove the inline enum/docstring, and extend DataframePlotDetailRenderer to use the helper and new normalization parameters.
    status: pending
    dependencies:
      - create-helper-module
  - id: integrate-motion-eeg
    content: Propagate normalization options through Motion/EEG datasources and their detail renderers, refactoring their normalization logic to use the shared helper while preserving defaults.
    status: pending
    dependencies:
      - create-helper-module
  - id: docs-and-cleanup
    content: Update docstrings and comments to reference ChannelNormalizationMode-based normalization and ensure behavior/backward compatibility are clearly described.
    status: pending
    dependencies:
      - wire-generic-renderer
      - integrate-motion-eeg
---

# Channel normalization enum and full integration plan

## 1. Introduce shared normalization helper module

- **Create `pypho_timeline/rendering/helpers/normalization.py`**:
- Define `ChannelNormalizationMode` enum with values: `NONE`, `GROUPMINMAXRANGE`, `INDIVIDUAL`, `ARBITRARY`.
- Add clear module-level docstring explaining intended usage across motion/eeg/eQuality, including **fixed examples that use tuples instead of lists as dict keys**:
    - `normalization_mode_dict = {('AccX','AccY','AccZ'): ChannelNormalizationMode.GROUPMINMAXRANGE, ...}`.
- Implement one or two focused helpers, e.g. `build_channel_mode_map(normalization_mode_dict, default_mode)` and `normalize_channels(df, channel_names, mode, normalization_mode_dict=None, arbitrary_bounds=None)`, which:
    - Supports per-channel mode resolution using the dict plus a default mode.
    - Implements the behaviors for `NONE` (raw), `GROUPMINMAXRANGE` (shared nanmin/nanmax per group), `INDIVIDUAL` (per-channel nanmin/nanmax), and `ARBITRARY` (from `arbitrary_bounds` or default [0, 1]).
- Keep helpers independent of any specific renderer to avoid circular imports.
- **Update `pypho_timeline/rendering/helpers/__init__.py`**:
- Import and add `ChannelNormalizationMode` (and the primary helper, e.g. `normalize_channels`) to `__all__` for convenient reuse.

## 2. Refactor `generic_plot_renderer.py` to use the shared enum

- **Clean up the existing inline enum and docstring** in [`pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py):
- Remove the current `ChannelNormalizationMode` definition and the stray `f""" ... """` block at lines 9–49.
- Replace them with a concise comment referring to the helper module, or import-time usage example pointing to `rendering.helpers.normalization`.
- **Import the shared enum**:
- Add `from pypho_timeline.rendering.helpers import ChannelNormalizationMode` (and any normalization helper) near the top of the file.
- Optionally re-export the enum via `__all__` if you want `ChannelNormalizationMode` discoverable from this module too, while keeping the single source of truth in `rendering.helpers.normalization`.

## 3. Extend `DataframePlotDetailRenderer` to support channel-wise normalization modes

- **Constructor/API changes in `DataframePlotDetailRenderer` (same file)**:
- Extend `__init__` signature to add:
    - `normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.GROUPMINMAXRANGE` (preserves current behavior of normalizing all channels together when `normalize=True`).
    - `normalization_mode_dict: Optional[dict] = None` for per-group/per-channel overrides using the tuple-keyed mapping.
    - `arbitrary_bounds: Optional[dict[str, tuple[float, float]]] = None `for `ARBITRARY` mode.
- Store these on `self` while keeping the existing `normalize: bool` flag for backward compatibility.
- **Normalization logic refactor**:
- Replace the current block that manually computes `min_vals`, `max_vals`, and `normalized_channel_df` with a call to the shared helper:
    - When `self.normalize` is `False`, keep existing raw-value behavior and skip helper.
    - When `self.normalize` is `True` and `self.normalization_mode_dict` is `None`, behave exactly as today by using `ChannelNormalizationMode.GROUPMINMAXRANGE` across `channel_names_to_use`.
    - When `self.normalization_mode_dict` is provided, call the helper to compute a normalized DataFrame honoring group- and channel-specific modes (including `INDIVIDUAL` and `ARBITRARY`).
- Use the returned normalized data in the plotting loop without changing the rest of the rendering logic.

## 4. Wire normalization modes from datasources to renderers

- **Motion datasource and renderer (`motion.py` and `motion_plot_renderer.py`)**:
- Update `MotionTrackDatasource.__init__` to accept optional normalization parameters, e.g. `normalization_mode: ChannelNormalizationMode | None = None`, `normalization_mode_dict: Optional[dict] = None`, and `arbitrary_bounds: Optional[dict] = None`, storing them on the instance.
- Extend `MotionPlotDetailRenderer.__init__` to accept and store the same normalization parameters (defaulting to existing behavior when not provided).
- In `MotionTrackDatasource.get_detail_renderer`, pass any configured normalization parameters into `MotionPlotDetailRenderer`.
- Inside `MotionPlotDetailRenderer.render_detail`, swap the raw `y_values = df_sorted[a_found_channel_name].values `pipeline for use of the shared `normalize_channels` helper, so motion channels can be normalized per group (e.g., accelerometer group vs gyro group) according to `ChannelNormalizationMode`.
- **EEG datasource and renderer (`eeg.py`)**:
- Mirror the same pattern in `EEGTrackDatasource.__init__` and `EEGTrackDatasource.get_detail_renderer` to accept and forward normalization settings.
- Update `EEGPlotDetailRenderer.__init__` to accept normalization parameters and default to the current behavior (normalizing all channels together), using `ChannelNormalizationMode.GROUPMINMAXRANGE` when no dict is supplied.
- Refactor the existing EEG normalization block (currently computing `normalized_channel_df` manually) to call the shared helper, so EEG and dataframe renderers share consistent normalization semantics.

## 5. Usage examples and documentation touch-ups

- **Centralize examples in the helper module**:
- Move and revise the multi-modality examples (Motion, eQuality, EEG) into `normalization.py`, ensuring they are syntactically valid (tuple keys) and show realistic patterns like: