---
name: Fix spectrogram HTML export
overview: The HTML export failures are caused by passing `hooks=` to `hv.Layout(...).opts(...)`, which recent HoloViews rejects. Move the Bokeh styling hook onto each channel element (Image/Overlay) before building the layout. Optionally harden session-summary `reset_index()` if you want the filename-mapping warning gone.
todos:
  - id: move-hooks-to-elements
    content: "In export_session_spectrograms_html: apply hooks=[_spectrogram_style_hook] to each channel plot element; remove hooks from hv.Layout.opts"
    status: completed
  - id: verify-html-export
    content: Re-run analysis with HTML export and confirm spectrogram_*.html files are written
    status: completed
  - id: optional-reset-index
    content: (Optional) Fix compute_session_summary_metrics reset_index when xdf_dataset_idx is both index and column
    status: completed
isProject: false
---

# Fix spectrogram HTML export (`hooks` on Layout)

## Root cause

In [`main_analyze_run.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/main_analyze_run.py), `SpectogramPlottingHelper.export_session_spectrograms_html` builds a vertical `hv.Layout` and applies:

```437:442:c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/main_analyze_run.py
				layout = layout.opts(
					title=session_title_display,
					shared_axes=True,
					hooks=[_spectrogram_style_hook]
				)
```

With your pinned stack ([`pyproject.toml`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/pyproject.toml): `holoviews>=1.20.2`, `bokeh>=3.4.3`), **`Layout` no longer supports the `hooks` option**, so `hv.save` fails with exactly: `Unexpected option 'hooks' for Layout type across all extensions`.

The hook itself is fine: `_spectrogram_style_hook` calls `_style_spectrogram_bokeh_plots` on the Bokeh root from `hv_plot.handles['plot']`.

## Recommended fix (minimal, targeted)

1. **Define `_spectrogram_style_hook` once** before the per-channel loop (same body as today).
2. **After each channel plot is finalized** (`img` alone, or `img * rects`), attach the hook to that **element**, not the layout:

   - `plot_el = (img * rects)` or `plot_el = img`
   - `plot_el = plot_el.opts(hooks=[_spectrogram_style_hook])`
   - `channel_plots.append(plot_el)`

3. **Keep** `hv.Layout(channel_plots).cols(1).opts(title=..., shared_axes=True)` **without** `hooks`.

This preserves the visual styling (title box, background, y-grid) per subplot, which matches the intent of the original hook.

4. **Sanity check**: Re-run the script with HTML export enabled and confirm files appear under `spectrograms_html` and open in a browser.

**Note:** [`export_combined_spectrograms_html`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/main_analyze_run.py) does not use `hooks` today; no change required there unless you later add the same styling.

## Optional: session summary WARN (`xdf_dataset_idx` already exists)

The line `tmp_df = stream_infos_df.reset_index()` in [`compute_session_summary_metrics`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/main_analyze_run.py) (around lines 157–165) can raise **`cannot insert xdf_dataset_idx, already exists`** if the dataframe already has both an index level named `xdf_dataset_idx` and a column with that name.

If you want that warning gone, adjust the reset logic (e.g. drop a redundant column before `reset_index`, or use index-aware logic only when the column is absent). This is independent of the HTML export bug.
