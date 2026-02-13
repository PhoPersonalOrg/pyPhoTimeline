---
name: MMB drag in all tracks
overview: Ensure middle-mouse-button (MMB) drag-to-pan works in all timeline tracks by letting the event reach the CustomViewBox even when the user starts the drag over child items (e.g. interval rects).
todos: []
isProject: false
---

# Implement MMB drag in all tracks

## Current state

- **CustomViewBox** in [pypho_timeline/widgets/custom_graphics_layout_widget.py](pypho_timeline/widgets/custom_graphics_layout_widget.py) already implements MMB drag as x-only pan (lines 241–256): `translateBy(x=-delta_x, y=0)`, so pan works when the pointer is over “empty” plot area.
- Every timeline track uses a plot backed by this CustomViewBox (via `CustomGraphicsLayoutWidget.addPlot` / root plot with `CustomViewBox`).
- Tracks add child items to the plot: **IntervalRectsItem** (overview/detail rects), PlotDataItem, image items, etc. In Qt/pyqtgraph, the **item under the cursor** receives the mouse press first. If that item does not ignore the event, it keeps the mouse grab and the ViewBox never receives the drag, so MMB pan does not work when the user starts the drag over those items.

## Root cause

- **IntervalRectsItem** in [pypho_timeline/rendering/graphics/interval_rects_item.py](pypho_timeline/rendering/graphics/interval_rects_item.py) overrides `mousePressEvent` (lines 349–360). It only calls `event.accept()` for right-click (context menu). For left and middle it does not call `accept()` or `ignore()`. In Qt, the default for overridden handlers can lead to the event being treated as handled, so the ViewBox may not receive MMB press/drag when the user starts over a rect.
- Other plot children (PlotDataItem, image, etc.) do not override mouse events, so they do not capture MMB. The only custom mouse handler in the rendering stack that could block MMB is IntervalRectsItem.

## Approach

- Have **IntervalRectsItem** explicitly **ignore** MMB in both press and release so the event propagates to the ViewBox. Then CustomViewBox’s existing MMB pan logic will run and MMB drag will work in all tracks, including when the drag starts over interval rects.

## Implementation

**File:** [pypho_timeline/rendering/graphics/interval_rects_item.py](pypho_timeline/rendering/graphics/interval_rects_item.py)

1. **mousePressEvent** (around line 349):
  - At the start of the handler, if `event.button() == QtCore.Qt.MouseButton.MiddleButton`, call `event.ignore()` and `return`.  
  - This lets MMB press propagate to the ViewBox so it can start the pan gesture.
2. **mouseReleaseEvent** (around line 361):
  - At the start of the handler, if `event.button() == QtCore.Qt.MouseButton.MiddleButton`, call `event.ignore()` and `return`.  
  - This keeps MMB release from being claimed by the item so the ViewBox can finish the pan gesture.

No changes to CustomViewBox or other files are required; MMB pan is already implemented and X-linking already syncs pan across tracks.

## Summary


| What            | Where                                                 | Action                                                                                                     |
| --------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| MMB pan logic   | CustomViewBox (already present)                       | None                                                                                                       |
| MMB propagation | IntervalRectsItem mousePressEvent / mouseReleaseEvent | Ignore MMB so ViewBox receives press and release; MMB drag then works in all tracks, including over rects. |


