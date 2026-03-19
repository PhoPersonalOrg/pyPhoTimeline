---
name: Fix visbrain pkg_resources crash
overview: "Fix the `ModuleNotFoundError: No module named 'pkg_resources'` crash caused by `visbrain` importing `pkg_resources` at startup. The fix makes the `TopoVB` import optional (defensive) and ensures the environment has setuptools installed."
todos:
  - id: guard-topo-import
    content: Wrap `TopoVB` import in try/except in `stream_viewer/renderers/__init__.py`
    status: completed
  - id: sync-env
    content: Run `uv sync` in stream_viewer to ensure setuptools/pkg_resources is installed, verify with `uv pip list`
    status: completed
isProject: false
---

# Fix visbrain pkg_resources Import Crash

## Root Cause

`visbrain` internally does `from pkg_resources import resource_filename` (in `visbrain/io/path.py`). `pkg_resources` is part of `setuptools`, which despite being listed in [pyproject.toml](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\pyproject.toml) line 32 as `setuptools>=75.3.2`, is either not installed or broken in the active `.venv`.

The crash happens because [stream_viewer/renderers/**init**.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\renderers__init__.py) unconditionally imports `TopoVB` at line 7, which triggers the full `visbrain` import chain.

## Fix

### 1. Make `TopoVB` import optional in `__init__.py`

Wrap the `TopoVB` import in a try/except in [stream_viewer/renderers/**init**.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\renderers__init__.py), matching the pattern already used for `HeatmapGPU` (commented out at lines 11-16):

```python
try:
    from stream_viewer.renderers.topo_vb import TopoVB
except ImportError:
    pass
```

This prevents `visbrain` issues from taking down the entire application.

### 2. Re-sync the environment

Run `uv sync` in the `stream_viewer` directory to ensure `setuptools` (and thus `pkg_resources`) is properly installed in `.venv`. This should resolve the underlying missing module.

If `uv sync` alone doesn't install setuptools into the venv (uv sometimes skips build-only deps), explicitly add it: `uv add setuptools` or verify it's present with `uv pip list | rg setuptools`.