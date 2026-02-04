---
name: Fix scipy simps import error
overview: Move the scipy.integrate.simps compatibility shim from __main__.py to __init__.py so it runs early when the package is imported, fixing the ImportError when running main.py directly.
todos:
  - id: add-shim-to-init
    content: Add scipy.integrate.simps compatibility shim to pypho_timeline/__init__.py at the very top (before any other imports)
    status: completed
  - id: remove-shim-from-main
    content: Remove the compatibility shim from pypho_timeline/__main__.py since it will be in __init__.py
    status: completed
    dependencies:
      - add-shim-to-init
---

# Fix scipy.integrate.simps ImportError

## Problem

When running `main.py` directly, an `ImportError` occurs because `scipy.integrate.simps` was removed in SciPy 1.12+ (replaced with `simpson`). The compatibility shim exists in `pypho_timeline/__main__.py`, but it only runs when that module is executed, not when the package is imported via `main.py`.

## Solution

Move the compatibility shim from `pypho_timeline/__main__.py` to `pypho_timeline/__init__.py` at the very top (before any other imports) so it executes whenever the package is imported, ensuring the shim is in place before any module tries to use `simps`.

## Changes

1. **Add compatibility shim to `pypho_timeline/__init__.py`**

- Place the shim at the very top of the file, before any other imports
- The shim tries to import `simps`, and if it fails, creates an alias from `simpson`

2. **Remove compatibility shim from `pypho_timeline/__main__.py`**

- Remove the shim code (lines 8-21) since it will now be in `__init__.py`
- Keep the rest of the file unchanged

## Files to Modify

- `pypho_timeline/__init__.py` - Add compatibility shim at the top
- `pypho_timeline/__main__.py` - Remove the compatibility shim (it's redundant now)

## Implementation Details

The shim will:

1. Try to import `simps` from `scipy.integrate` (works for old SciPy versions)
2. If that fails, import `simpson` and create `scipy.integrate.simps = simpson` as an alias
3. This ensures backward compatibility with both old and new SciPy versions