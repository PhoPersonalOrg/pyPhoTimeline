---
name: VLC context menu video track
overview: Add a "Show in VLC..." item to the video track’s interval context menu by extending [IntervalRectsItem](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/interval_rects_item.py) with an optional callback (same pattern as "Render detailed") and wiring it from [track_renderer.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py) for `VideoTrackDatasource` only, reusing existing VLC launch helpers in [video.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py).
todos:
  - id: interval-rects-callback
    content: Add show_in_vlc_callback + QAction + _on_show_in_vlc to IntervalRectsItem.__init__ and getContextMenus
    status: completed
  - id: track-renderer-wire
    content: For VideoTrackDatasource, define show_in_vlc_callback and pass to build_IntervalRectsItem_from_interval_datasource; import VLC helpers from video.py
    status: completed
isProject: false
---

# "Show in VLC..." on video interval context menu

## Behavior

- On **right**-click on a video interval bar (existing `IntervalRectsItem` flow: `[mousePressEvent` stores `\_context_menu_event_pos](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/interval_rects_item.py)`, `[raiseContextMenu` → `getContextMenus](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/interval_rects_item.py)`), the menu includes **"Show in VLC..."** (in addition to existing items).
- Choosing it opens the file for the **hit interval** in VLC at offset `click_x - t_start` (same semantics as thumbnail double-click), using `**click_t = float(\_context_menu_event_pos.x())`** in item/plot coordinates (your log’s x ~ `1775007517` matches timeline time).
- Reuse `**VlcLaunchableVideoThumbnailImageItem.launch_video_player_vlc`** and `**VideoThumbnailDetailRenderer.scalar_interval_t_start_to_unix_seconds` / `scalar_interval_t_duration_seconds`** from `[video.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py)` — no duplicate VLC discovery/launch logic.

## Code changes

### 1. `[interval_rects_item.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/interval_rects_item.py)`

- Extend `**__init__(..., detail_render_callback=None, show_in_vlc_callback=None)**` (add optional `show_in_vlc_callback: Optional[Callable[[int, float], None]]` — `rect_index`, `click_t`).
- Store as `**self._show_in_vlc_callback**`.
- In `**getContextMenus**`, when `self.menu is None` and `**self._show_in_vlc_callback is not None**`, add `**QAction("Show in VLC...")**` (place it next to **"Render detailed"** for discoverability), `**triggered`** → `**_on_show_in_vlc`**.
- Implement `**_on_show_in_vlc`** (mirror `**_on_render_detailed**`): resolve `**rect_index**` via `**_get_rect_at_position(self._context_menu_event_pos)**`; if `None`, return (optional: log debug); else `**click_t = float(self._context_menu_event_pos.x())**`, call `**self._show_in_vlc_callback(rect_index, click_t)**`.
- Keep `**Render2DEventRectanglesHelper.build_IntervalRectsItem_from_interval_datasource**` as-is: it already passes `****kwargs**` into `**IntervalRectsItem**` (`[render_rectangles_helper.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/helpers/render_rectangles_helper.py)` line 106), so the new kwarg flows automatically.

### 2. `[track_renderer.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py)`

- When building `**detail_render_callback**` for the pyqtgraph overview (existing block ~268–313), **also** define `**show_in_vlc_callback`** **only if** `**VideoTrackDatasource is not None and isinstance(self.datasource, VideoTrackDatasource)`**.
- Handler body:
  - Bounds-check `**rect_index`** against `**self._overview_df`** (same as detail callback).
  - Row = `**self._overview_df.iloc[rect_index]**`; `**video_file_path**`; normalize `**t_start` / `t_duration**` with `**VideoThumbnailDetailRenderer.scalar_***`; clamp `**offset = click_t - t_start_sec**` to `**[0, t_duration_sec]**`; resolve parent via `**VlcLaunchableVideoThumbnailImageItem.message_box_parent_for_plot_item(self.plot_item)**`; call `**VlcLaunchableVideoThumbnailImageItem.launch_video_player_vlc(Path(...), offset, parent)**`.
- Import `**VideoThumbnailDetailRenderer**` and `**VlcLaunchableVideoThumbnailImageItem**` from `**pypho_timeline.rendering.datasources.specific.video**` (or only the thumbnail item if you re-export helpers there — prefer importing the two symbols from `**video**` as today).
- Pass `**show_in_vlc_callback=show_in_vlc_callback**` into the existing `**build_IntervalRectsItem_from_interval_datasource(...)**` call (~311).

## Notes

- **Vispy** video path does not use `**IntervalRectsItem`**; this menu appears only for the **pyqtgraph** overview path (matches your log).
- **Thumbnails**: unchanged; this adds a second, reliable entry point from the interval bar.
- **Colocation**: keep VLC launch implementation on `**VlcLaunchableVideoThumbnailImageItem`**; `**TrackRenderer`** only orchestrates row lookup + scalar conversion + one method call.

## Verification

- Right-click a video interval → **"Show in VLC..."** appears; choosing it opens the correct file at approximately the clicked time.
- Non-video tracks: no extra item (callback not passed).
- Missing VLC / missing file: existing `**QMessageBox`** paths still apply.

