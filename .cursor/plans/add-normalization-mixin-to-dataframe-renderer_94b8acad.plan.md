---
name: add-normalization-mixin-to-dataframe-renderer
overview: Refactor DataframePlotDetailRenderer to use ChannelNormalizationModeNormalizingMixin so normalization config is centralized and reusable across renderers.
todos: []
---

# Add ChannelNormalizationModeNormalizingMixin to DataframePlotDetailRenderer

### Goals

- **Reuse shared normalization logic** in `ChannelNormalizationModeNormalizingMixin` for `DataframePlotDetailRenderer`.
- **Centralize normalization configuration/state** (modes, bounds, flags) on the renderer instance instead of partially duplicating it.
- **Minimize API breakage** while keeping your single-line signature and call-style preferences.

### Steps

- **Update imports** in [`pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py) to include `ChannelNormalizationModeNormalizingMixin` from the normalization helpers module.
- **Change the base class** of `DataframePlotDetailRenderer` to inherit from `ChannelNormalizationModeNormalizingMixin` alongside `DetailRenderer`, ensuring the MRO is compatible (e.g., `class DataframePlotDetailRenderer(ChannelNormalizationModeNormalizingMixin, DetailRenderer):`).
- **Refactor `__init__`** of `DataframePlotDetailRenderer` to:
- Keep the existing public parameters (including normalization-related ones) on a **single-line signature** where possible.
- Call `ChannelNormalizationModeNormalizingMixin.__init__` with `channel_names`, `fallback_normalization_mode`, `normalization_mode_dict`, `arbitrary_bounds`, and `normalize`.
- Optionally introduce and pass `normalize_over_full_data` and `normalization_reference_df` with sensible defaults, matching `ChannelNormalizationModeNormalizingMixin` semantics.
- Preserve current color/pen setup code, only moving it after the mixin and `DetailRenderer` initialization.
- **Update `render_detail`** in `DataframePlotDetailRenderer` to:
- Use `self.channel_names` and the mixin’s `compute_normalized_channels` where normalization is enabled instead of calling `normalize_channels` directly.
- Keep the auto-detection logic for `channel_names` when `self.channel_names` is `None`, and then feed the resolved list into `compute_normalized_channels`.
- Maintain existing behavior for the non-normalized path (when `normalize` is false), using raw values.
- **Leave `get_detail_bounds` and clearing logic unchanged** initially, since they operate on the raw data and are independent of the normalization mixin; only adjust them later if you decide bounds should also respect normalized ranges.
- **Run tests / manual checks** (e.g., opening a dataframe-based track in the timeline) to confirm:
- Visual output matches previous behavior when normalization params are the same.