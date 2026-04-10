---
name: repair main window ui
overview: Fix the `MainTimelineWindow` startup crash by realigning the loaded Qt UI with the Python code that initializes the log panel and collapsed-dock footer controls.
todos:
  - id: inspect-ui-contract
    content: Patch `MainTimelineWindow.ui` so it provides a real `logPanel` widget instead of only `logPanelLayout`.
    status: completed
  - id: align-footer-names
    content: Resolve any `collapsedDockOverflowStrip` and action-name mismatches between the UI file and `MainTimelineWindow.py`.
    status: completed
  - id: smoke-validate-window
    content: Re-run the timeline construction path and verify log toggle and footer controls initialize cleanly.
    status: completed
isProject: false
---

# Repair `MainTimelineWindow` UI Contract

## Root Cause
`[MainTimelineWindow.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py)` assumes `loadUi()` creates a widget named `logPanel`:

```40:47:c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py
    def initUI(self):
        self.statusBar().hide()
        content_layout = QVBoxLayout(self.contentWidget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.contentWidget.setLayout(content_layout)
        self._log_widget = LogWidget(parent=self.logPanel)
        self.logPanel.layout().addWidget(self._log_widget)
        self.logPanel.setVisible(False)
```

But `[MainTimelineWindow.ui](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.ui)` only defines a bare layout named `logPanelLayout`, not a widget named `logPanel`, so `self.logPanel` is never created.

## Proposed Changes
- Update `[MainTimelineWindow.ui](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.ui)` so the log row is wrapped in a real `QWidget` named `logPanel`, with `logPanelLayout` nested inside it.
- Keep the existing Python-side `LogWidget(parent=self.logPanel)`, `self.logPanel.layout().addWidget(...)`, and `self.logPanel.setVisible(...)` behavior unchanged if the UI repair fully restores the expected contract.
- Align the collapsed-dock footer object naming in the UI or Python so `attach_collapsed_dock_overflow()` can find both `collapsedDockOverflowContents` and the strip widget it wants to show/hide.
- Review the footer navigation action names in the UI versus `[MainTimelineWindow.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py)` and normalize them if any action hookups are currently skipped by `hasattr(...)` guards.

## Validation
- Rebuild the timeline through `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` using the same `build_from_xdf_files(...)` notebook call and confirm `MainTimelineWindow` initializes without `AttributeError`.
- Verify the footer `Show Log` toggle expands/collapses the embedded log panel correctly.
- Verify collapsed dock overflow controls appear when docks are collapsed.
- Smoke-test footer jump and prev/next actions to confirm no remaining name drift between `.ui` and Python.
