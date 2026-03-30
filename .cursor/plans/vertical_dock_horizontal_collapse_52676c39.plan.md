---
name: Vertical dock horizontal collapse
overview: Fix `Dock.hideContents` so docks with a left (vertical) title bar shrink along **x** (horizontal collapse / column width), while top (horizontal) title bars keep the existing splitter-orientation logic (shrink **y** in vertical stacks, **x** in horizontal splits).
todos:
  - id: hidecontents-vertical-title
    content: "Update Dock.hideContents: vertical title bar → setStretch(cw, sy); adjust non-splitter fallback; keep horizontal title logic unchanged"
    status: completed
  - id: manual-verify
    content: Manually verify vertical stack + left-title dock + side-by-side column; horizontal split layouts
    status: completed
isProject: false
---

# Vertical title bar: horizontal collapse stretch

## Problem

`[hideContents](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)` picks the collapsed stretch axis from the **parent** `[QSplitter](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)` only:

```465:483:c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py
    def hideContents(self):
        ...
        if isinstance(c, QtWidgets.QSplitter):
            if _qsplitter_orientation_is_vertical(c):
                self.setStretch(sx, cw)
            else:
                self.setStretch(cw, sy)
        else:
            self.setStretch(sx, cw)
```

How containers use `(wx, wy)` (`[Container.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Container.py)`):

- **VContainer** (vertical splitter): `setSizes` from each child’s `**wy`**; aggregate `**wx`** is `max(wx)` → drives **column width** when this container is a pane in an outer **HContainer**.
- **HContainer** (horizontal splitter): `setSizes` from each child’s `**wx`**.

For a dock with `**orientation == 'vertical'`** (title on the left; see `[updateStyle](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)`), hiding `widgetArea` frees space along the **horizontal** direction (content was beside the label). Reducing `**sy`** in a vertical stack wrongly shrinks **row height** and leaves the column-width behavior unchanged. The correct knob is `**sx` → cw** so the column’s `max(wx)` can drop and neighbors (e.g. a wide log column) get width.

Docks with `**orientation == 'horizontal'`** (title on top) stay as today: vertical parent → `(sx, cw)`; horizontal parent → `(cw, sy)`.

## Implementation (single file)

**File:** `[pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)`

1. **Refine `hideContents`** after saving `(sx, sy)` and hiding `widgetArea`:
  - If `self.orientation == 'vertical'`: always `**self.setStretch(cw, sy)**` (horizontal collapse), for both vertical and horizontal splitter parents (same result either way).
  - Else (`'horizontal'` or `'auto'` resolved to horizontal via `setOrientation`): keep current branch on `isinstance(c, QSplitter)` and `_qsplitter_orientation_is_vertical` as today.
  - **Non-splitter parent** fallback: today uses `(sx, cw)`. For vertical title bar use `(cw, sy)`; for horizontal title bar keep `(sx, cw)` to match timeline’s vertical-column default from the prior plan.
2. **Optional clarity:** extract a tiny local helper or a short comment block documenting the 2×2 matrix (title orientation × parent splitter) so future edits do not regress.

**No changes** to `[showContents](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)` (already restores `_stretch_before_content_toggle`).

## Verification

- Timeline: stack of **horizontal** title docks in a column; collapse still frees **height** (no empty band).
- Same layout with a dock switched to **vertical** title (orientation button / auto): collapse frees **width** at the column level when an **HContainer** splits that column from another (e.g. spectrogram column vs log).
- Horizontal split (e.g. “Split All Tracks”): **horizontal** title → collapse still uses width; **vertical** title → still `setStretch(cw, sy)` (width along split).

## Note on `'auto'` orientation

`self.orientation` is updated in `[setOrientation](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)` when not `None`, so collapse should follow the **effective** bar direction at click time.