---
name: Fix icon build failure
overview: The PyInstaller build fails because the spec requires icon files that do not exist in the repo. Making icon inclusion optional in the spec allows the build to succeed; the app already handles a missing icon at runtime.
todos: []
isProject: false
---

# Fix icon-related PyInstaller build failure

## Problem

Build fails with:
`FileNotFoundError: Data file not found: ...\icons\stream_viewer icon_no_bg2.ico`

- The spec file uses `get_data_path('icons', 'stream_viewer icon_no_bg2.ico', ...)` which **requires** the file to exist.
- The [stream_viewer](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer) repo has **no `icons/` directory** and no `.ico`/`.png` icon files (search confirmed 0 matches).
- [main.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\applications\main.py) already treats the icon as optional (lines 867–872: only sets window icon if `ico_path.exists()`).

## Approach

Make icon paths **optional** in the spec so the build succeeds with or without icon files. No new assets or repo layout changes required.

## Changes

### 1. [lsl_viewer.spec](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\lsl_viewer.spec)

- **Add an optional-data helper** (e.g. `get_data_path_optional(*path_parts, target_dir)`) that returns a tuple `(abs_path, target_dir)` only if the file exists, otherwise returns `None`. Build a `datas` list by appending only non-None results.
- **Use it for both icon entries**: call the optional helper for `stream_viewer icon_no_bg2.ico` and `stream_viewer icon_no_bg2.png`; include in `datas` only when present.
- **EXE icon (line 126)**: keep using `project_root / 'icons' / 'stream_viewer icon_no_bg2.ico'` only if that path exists; otherwise pass `icon=None` so PyInstaller does not require the file.

### 2. [BUILD_EXECUTABLE.md](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\BUILD_EXECUTABLE.md)

- In **Troubleshooting** (or a short **Optional assets** section), state that application/window icons are optional: if `icons/stream_viewer icon_no_bg2.ico` and `icons/stream_viewer icon_no_bg2.png` exist at project root they will be bundled and used; otherwise the build still succeeds and the app runs without a custom icon.

## Result

- Build succeeds when `icons/` or icon files are missing.
- If you add `icons/stream_viewer icon_no_bg2.ico` and `.png` later, they will be included and used without further spec changes.
