# Purpose

Currently a very good multi-track timeline for rendering the EEG/Motion/VideoFile/NoteMessages modalities that have been saved out to XDF.
As of 2026-01-08, this is the most-promising way of seeing the data for analysis.

This is an experimental independent attempt at extracting the pyqtgraph-based timeline functionality of pyPhoCorePlaceAnalysis and helpers into an independent (decoupled) library so it can be used in other projects (like EEG analysis).



# Usage

```
(py-pho-timeline) PS H:\TEMP\Spike3DEnv_ExploreUpgrade\Spike3DWorkEnv\pyPhoTimeline> python -m pypho_timeline
============================================================
pyPhoTimeline Example
============================================================
Adding overview track...
Adding window-synchronized track...
Adding global data track...

Timeline widget created with 3 example tracks:
  1. Overview track (NO_SYNC) - shows full time range
  2. Window track (TO_WINDOW) - syncs with active window
  3. Global track (TO_GLOBAL_DATA) - one-time sync to global range

The window will automatically scroll to demonstrate synchronization.
Close the window to exit.


Demonstrating window scrolling...
Window scrolled to: 40.00 - 55.00
Window scrolled to: 50.00 - 65.00
Window scrolled to: 60.00 - 75.00

```

# GitHub Codespaces setup

## Automated Setup (Recommended)

The project includes a **development container configuration** (`.devcontainer/devcontainer.json`) that automates the entire setup process for GitHub Codespaces.

1. Click the green **Code** button on GitHub
2. Select **Codespaces** → **Create codespace on master**
3. Wait for the container to initialize (automatic setup runs)
4. Start developing!

The dev container automatically:
- Installs UV package manager
- Sets up dependencies in dev or release mode (with fallback)
- Configures Python interpreter and VS Code extensions
- Enables debugging and testing out-of-the-box

For details, see [.devcontainer/README.md](.devcontainer/README.md).

## Manual Setup (Local Development)

If setting up locally without dev containers:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install git+https://github.com/PhoPersonalOrg/uv-deps-switcher.git
uv-deps-switcher dev
uv sync --all-extras
source .venv/bin/activate
```



## PyQt5
```toml
 - pyqt5==5.15.11
 - pyqt5-qt5==5.15.2
 - pyqt5-sip==12.17.2
 - pyqt5singleton==0.1
 - sip==6.15.0
```
