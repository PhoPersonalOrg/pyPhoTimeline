---
name: VLC double-click video track
overview: Port the PhoOfflineEEGAnalysis `VideoMetadataTrack` VLC launch logic (executable discovery, subprocess flags, start offset, QMessageBox errors) into pyPhoTimeline by extending [video.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py) so double-clicking a rendered video thumbnail opens the file in VLC at the clicked timeline offset.
todos:
  - id: helpers-vlc
    content: Add _find_vlc_executable + _launch_video_player_vlc in video.py (qtpy QMessageBox, same semantics as VideoMetadataTrack @ 42e26bb).
    status: completed
  - id: thumbnail-item
    content: "Subclass pg.ImageItem: accept left clicks, mouseDoubleClickEvent maps scene→view x, clamp offset, call launch helper; normalize t_start via datetime_to_unix_timestamp."
    status: completed
  - id: wire-render
    content: In VideoThumbnailDetailRenderer.render_detail, use subclass when video_file_path present and non-empty; else keep plain ImageItem.
    status: completed
isProject: false
---

# VLC double-click on video thumbnails (`video.py`)

## Reference behavior (`[VideoMetadataTrack` @ 42e26bb]([https://github.com/PhoPersonalOrg/PhoOfflineEEGAnalysis/blob/42e26bb/src/phoofflineeeganalysis/analysis/UI/timeline/tracks/VideoMetadataTrack.py](https://github.com/PhoPersonalOrg/PhoOfflineEEGAnalysis/blob/42e26bb/src/phoofflineeeganalysis/analysis/UI/timeline/tracks/VideoMetadataTrack.py)))

- Resolve `**video_file_path**` for the interval; validate path exists.
- Compute **start offset in the file**: `click_x_on_timeline - interval_t_start`, clamped to `[0, t_duration]` (same axis as the plot / interval).
- Find **VLC**: `shutil.which('vlc')`, then common Windows / macOS / Linux paths (mirroring the reference).
- **Launch**: `subprocess.Popen([vlc, "--start-time", str(int(offset_seconds)), str(video_path)], ...)` with `CREATE_NO_WINDOW` on Windows and `stdout`/`stderr` to `DEVNULL`; Unix uses `start_new_session=True`.
- **Errors**: `QMessageBox.warning` / `critical` when path missing, file missing, VLC not found, or launch exception.

## Target code (`[video.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py)`)

- `**VideoTrackDatasource` / `video_metadata_to_intervals_df`** already carry `**video_file_path`** and `**t_start` / `t_duration`**. No datasource changes required unless you want a feature flag (optional; default can be “always on” like the reference).
- `**VideoThumbnailDetailRenderer.render_detail`**: Today each frame is a plain `pg.ImageItem` (~321–331). Replace with a **small subclass** of `pg.ImageItem` that:
  - Calls `setAcceptedMouseButtons(QtCore.Qt.LeftButton)` (and `setAcceptHoverEvents(True)` if needed) so the item receives clicks above the track.
  - Stores `**video_path`**, `**t_start_sec`**, `**t_duration_sec**` (floats), computed from the interval row using the same rules as `get_detail_bounds` (use existing `[datetime_to_unix_timestamp](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/utils/datetime_helpers.py)` when `t_start` is `datetime` / `pd.Timestamp`—absolute mode intervals may use timezone-aware timestamps).
  - Overrides `**mouseDoubleClickEvent**`: `scene_pos = event.scenePos()`, map with `plot_item.getViewBox().mapSceneToView(scene_pos)`, use `view_pos.x()` as timeline time, then offset = `x - t_start_sec`, clamp, then call shared launch helper.
  - Resolves a **QMessageBox parent** via `plot_item.scene().views()[0].window()` when available, else `None`.
- **Module-level helpers** (keeps renderer small; mirrors reference):

```text
  _find_vlc_executable() -> Optional[Path]
  _launch_video_player_vlc(video_path: Path, start_offset_seconds: float, parent_widget: Optional[QWidget]) -> None
  

```

  Match reference branches for Windows / Darwin / Linux paths; use `getattr(subprocess, "CREATE_NO_WINDOW", 0)` if you want a safe fallback.

- **Imports** (qtpy-aligned with the rest of the project): add `os`, `platform`, `shutil`, `subprocess`, and `from qtpy.QtWidgets import QMessageBox` (keep `QtCore` as today).

## Out of scope / follow-ups

- **Vispy video path** (`[vispy_video_epoch_renderer.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py)` / `[track_renderer.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py)`): thumbnails are pyqtgraph `ImageItem`s; vispy.epoch view would need separate input handling if you want VLC there too.
- **Single-click metadata dialog** from the reference is not present in pyPhoTimeline’s video detail renderer; only double-click → VLC unless you ask to add it.

## Verification

- Double-click a thumbnail on a video interval: VLC opens with `start-time` roughly matching horizontal click position.
- Missing VLC / missing file / bad path: QMessageBox appears; no crash.
- Smoke-test on Windows (primary) and note Unix flags.

