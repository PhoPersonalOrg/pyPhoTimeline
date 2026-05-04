---
name: Dose plot legend
overview: Enable PyQtGraph’s built-in legend for dose curve detail plots by ensuring `addLegend()` runs before curves are added. Curve labels already come from `PlotDataItem`’s `name=` in `DataframePlotDetailRenderer`; only dose-specific wiring is needed in `dose.py`.
todos:
  - id: dose-renderer-subclass
    content: "Add DoseCurvePlotDetailRenderer in dose.py: guard + addLegend(offset, labelTextColor, brush) then super().render_detail"
    status: completed
  - id: wire-get-detail-renderer
    content: Return DoseCurvePlotDetailRenderer from DoseTrackDatasource.get_detail_renderer with same kwargs as today
    status: completed
isProject: false
---

# Add top-right legend for DOSE curve plots

## Root cause

- [`DataframePlotDetailRenderer.render_detail`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\generic_plot_renderer.py) already creates each series with `name=channel_name` (line ~442), which matches PK/PD column names (`AMPH_gut`, `DA_str`, etc.).
- PyQtGraph only registers those names in a legend when [`PlotItem.addLegend`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\graphicsItems\PlotItem\PlotItem.py) has been called so `plot_item.legend` is non-`None`. Otherwise `addItem` skips the `legend.addItem` branch (~583–584).
- [`DoseTrackDatasource.get_detail_renderer`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\dose.py) returns a plain `DataframePlotDetailRenderer`; nothing calls `addLegend`.

## Approach (dose-only, minimal blast radius)

1. **Add a small subclass** in [`dose.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\dose.py) (e.g. `DoseCurvePlotDetailRenderer`) inheriting `DataframePlotDetailRenderer`, overriding `render_detail` to:
   - Apply the same early guards as the parent would (`None`/empty/non-DataFrame `detail_data` → return `[]` or re-raise) so we do not attach an orphan legend on unusable data.
   - Call `plot_item.addLegend(offset=(-10, 10), labelTextColor='w', brush=...)` **before** `super().render_detail(...)`.
     - **Position**: PyQtGraph’s `LegendItem` derives anchor from offset sign: **negative x** anchors the legend to the **right** of the view box; **positive y** with that logic maps to the **top** side — use something like `offset=(-10, 10)` or `(-15, 12)` for a clear top-right inset (same pattern as the docstring example in [`GraphicsWidgetAnchor`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\graphicsItems\GraphicsWidgetAnchor.py): `itemPos=(1,0), parentPos=(1,0), offset=(-10,10)` for upper-right).
     - **Readability on dark UI**: pass `labelTextColor='w'` and a semi-transparent dark `brush` (e.g. RGBA tuple) so labels match the screenshot’s dark plot.
   - `addLegend` is idempotent: if `plot_item.legend` already exists, PyQtGraph returns it; re-renders still work because [`clear_detail`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\generic_plot_renderer.py) uses `removeItem`, which removes entries from the existing legend (`PlotItem.removeItem` ~643–644).

2. **Point `get_detail_renderer`** at `DoseCurvePlotDetailRenderer` with the same constructor kwargs currently passed to `DataframePlotDetailRenderer` (no behavior change except legend).

## Files to change

- **[`pypho_timeline/rendering/datasources/specific/dose.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\dose.py)** only: new subclass + swap the class in `get_detail_renderer`.

## Out of scope

- No change to [`generic_plot_renderer.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\generic_plot_renderer.py) unless you later want legends on all dataframe tracks (MOTION/EEG would inherit it).

## Verification

- Open a timeline with `DOSE_CURVES_Computed` (or equivalent) detail view: legend should appear **top-right** with one row per visible curve channel name; panning/resizing the view should keep the legend anchored; switching intervals should refresh curve entries without duplicate legends.
