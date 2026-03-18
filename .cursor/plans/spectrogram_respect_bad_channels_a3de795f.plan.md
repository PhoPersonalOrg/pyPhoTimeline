---
name: Spectrogram respect BAD channels
overview: Update `raw_spectogram_working` so spectrogram computation uses only channels not in `raw.info["bads"]` (set by `time_independent_bad_channels` or manually), and fix the existing loop so channel indices align with the data array.
todos: []
isProject: false
---

# Spectrogram respect BAD channels and bad-annotated times

## Current behavior

- **[EEG_data.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\EEG_data.py)** `raw_spectogram_working` (lines 314–390):
  - Uses `picks = mne.pick_types(raw.info, eeg=True, meg=False)` when `picks is None`. MNE’s `pick_types` **excludes** `raw.info["bads"]` by default (`exclude='bads'`), so bad channels are already omitted from `picks` when present.
  - Gets `data` with `raw.get_data(picks=picks)`, so `data` has shape `(len(picks), n_times)` (only picked channels).
  - Bug: it then uses `ch_names = deepcopy(raw.info.ch_names)` (all channels) and loops `for ch_idx, a_ch in enumerate(raw.info.ch_names)` and uses `data[ch_idx]`. So it indexes `data` by full channel index instead of by row index in `data`, which is wrong whenever there are non-EEG channels or when bads are excluded (channel count ≠ data rows).
- `**time_independent_bad_channels`** (lines 393–447) appends detected bad channels to `raw.info["bads"]`, so any later call to `raw_spectogram_working` will see those bads only if we both (1) exclude bads when building `picks` and (2) use the picked subset consistently for names and loop.

## Required changes (minimal)

All edits in [EEG_data.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\EEG_data.py) inside `raw_spectogram_working`:

1. **Exclude bad channels from `picks`**
  - When `picks is None`: keep `picks = mne.pick_types(raw.info, eeg=True, meg=False)` (already excludes bads by default). Optionally make it explicit: `exclude='bads'` for clarity.
  - When `picks` is provided: filter out any channel that is in `raw.info["bads"]` so that BAD channels (from `time_independent_bad_channels` or manual marking) are never used:
  - e.g. `bads = set(raw.info.get("bads") or [])` then if `picks` is not None, `picks = [p for p in picks if raw.info.ch_names[p] not in bads]` (for index-based picks) or the equivalent if picks are channel names, depending on MNE’s type for `picks`).
2. **Use only picked channels for names and loop**
  - Set `ch_names` from the picked channels only, e.g. `ch_names = [raw.info.ch_names[i] for i in picks]`.
  - Loop over the rows of `data`, not over all channel names: e.g. `for i, ch_idx in enumerate(picks):`, then `a_ch = raw.info.ch_names[ch_idx]`, and use `data[i]` (not `data[ch_idx]`) for `spectrogram(...)`. This aligns indices with `get_data(picks=picks)` and ensures only good channels get spectrograms.
3. **Docstring**
  - Short note that BAD channels (e.g. from `time_independent_bad_channels`) are excluded from the computation, in addition to optional masking of bad-annotated time segments.

## Result

- Bad-annotated time segments continue to be masked when `mask_bad_annotated_times=True`.
- BAD channels (from `time_independent_bad_channels` or `raw.info["bads"]`) are excluded from spectrogram computation and from the returned `ch_names` / `spectogram_result_dict` / `Sxx` / `Sxx_avg`.
- No change to the return structure; only the set of channels and the index-vs-name alignment are fixed.

## Optional

- Add a one-line comment above the `picks` logic: e.g. “Exclude BAD channels (e.g. from time_independent_bad_channels) so they are not included in spectrograms.”

