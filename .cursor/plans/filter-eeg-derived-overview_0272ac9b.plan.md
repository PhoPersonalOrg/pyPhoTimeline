---
name: filter-eeg-derived-overview
overview: Exclude computed EEG helper tracks (Spectrogram, GFP, and similar derived EEG tracks) from the interval overview strip while keeping base EEG tracks visible.
todos:
  - id: add-overview-track-filter
    content: Implement a helper in simple_timeline_widget.py that returns overview-eligible primary track names and excludes EEG-derived datasource classes while keeping base EEG.
    status: completed
  - id: apply-filter-at-overview-callsites
    content: Use the helper in add_timeline_overview_strip, _resync_timeline_overview_datasource_connections, and _rebuild_timeline_overview_strip.
    status: completed
  - id: verify-behavior
    content: Run a quick functional check with EEG + derived tracks to confirm derived tracks are omitted from overview and base EEG remains visible.
    status: completed
isProject: false
---

# Exclude EEG-Derived Tracks From Overview Strip

## Goal
Ensure the interval overview strip only shows primary, user-facing tracks and omits EEG-derived helper tracks (e.g., spectrogram/GFP derivatives), while still showing the base EEG track.

## Proposed Changes
- Add a focused filtering helper in [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py) that:
  - starts from `get_track_names_for_window_sync_group(window_sync_group='primary')`
  - inspects each track datasource from `self.track_datasources`
  - excludes EEG-derived datasource types (initially `EEGSpectrogramTrackDatasource`, `EEGFPTrackDatasource`; extensible for future EEG-derived helper classes)
  - keeps `EEGTrackDatasource` (base EEG) included
- Replace direct calls used by overview-strip wiring with this filtered list at:
  - overview dock initial sizing in `add_timeline_overview_strip(...)`
  - datasource signal re-sync in `_resync_timeline_overview_datasource_connections(...)`
  - strip rebuild in `_rebuild_timeline_overview_strip(...)`

## Validation
- Build timeline with base EEG + derived spectrogram/GFP tracks.
- Confirm `timeline_overview_strip` rows do not include derived EEG tracks.
- Confirm base EEG remains visible in the overview strip.
- Verify track add/remove and datasource update signals still trigger overview rebuild correctly.