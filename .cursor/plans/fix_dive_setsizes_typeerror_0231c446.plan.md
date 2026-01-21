---
name: Fix DIVE setSizes TypeError
overview: Fix the TypeError in dive_manager.py where splitter.setSizes() receives float values instead of integers. Convert the calculated sizes to integers before passing them to setSizes().
todos: []
---

# Fix DIVE setSizes TypeError

## Problem

The `dive_example.py` script fails with a `TypeError` when initializing `DIVEWidget`. The error occurs at line 170 in `DIVE\_components\dive_manager.py`:

```
TypeError: index 0 has type 'float' but 'int' is expected
```

The issue is that `splitter.setSizes()` expects a list of integers, but the code passes float values from the multiplication operations (`splitter.size().width() * 0.1`, etc.).

## Solution

Convert the float values to integers in the `setSizes()` call at line 170 of [`DIVE\_components\dive_manager.py`](DIVE\_components\dive_manager.py).

## Changes Required

1. **Fix line 170 in `dive_manager.py`**: Wrap each size calculation with `int()` to convert floats to integers:

   - Change: `splitter.setSizes([splitter.size().width() * 0.1, splitter.size().width() * 0.8, splitter.size().width() * 0.1])`
   - To: `splitter.setSizes([int(splitter.size().width() * 0.1), int(splitter.size().width() * 0.8), int(splitter.size().width() * 0.1)])`

This is a