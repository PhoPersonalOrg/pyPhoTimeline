---
name: MaskedValidDataFrame accessor
overview: Implement the stub `MaskedValidDataFrame` pandas accessor in PhoPyMNEHelper so callers can produce a DataFrame view/copy with selected columns replaced by `pd.NA` where a boolean mask column is False, using row-wise `where` for low overhead on the masked slice only.
todos:
  - id: refactor-accessor-base
    content: Detach MaskedValidDataFrame from CommonDataFrameAccessorMixin; keep _obj + optional light _validate
    status: completed
  - id: implement-apply-mask
    content: Add apply_mask(mask_col, value_cols, copy=...) using row-wise where; validate columns
    status: completed
  - id: docstring-cleanup
    content: Align docstring and usage example with real API and semantics
    status: completed
isProject: false
---

# Implement `MaskedValidDataFrame` (`masked_df`)

## Current state

- File: `[PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)`
- `MaskedValidDataFrame` is registered as `df.masked_df` but has **no methods**; docstring describes row-wise masking by one boolean column.
- It subclasses `[CommonDataFrameAccessorMixin](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)` which imposes `_required_column_names = ['start', 'stop', 'label', 'duration']` and epoch-oriented `extra_data_*` properties. That is **misleading and wrong** for arbitrary tabular data (and `extra_data_column_names` would drop unrelated “required” columns).

## Design decisions

1. **Stop inheriting `CommonDataFrameAccessorMixin`** for `MaskedValidDataFrame`. Use a small standalone class (or a minimal private base with only `_obj`) so epoch helpers are not mixed into a generic mask utility.
2. **API (single clear entry point):** e.g. `df.masked_df.apply_mask(mask_col: str, value_cols: Sequence[str], *, copy: bool = True) -> pd.DataFrame`
  - Semantics match the docstring: where `mask_col` is **True**, keep values in `value_cols`; where **False**, set those cells to `pd.NA`.
  - Implementation: `self._obj[value_cols].where(self._obj[mask_col], pd.NA)` for the affected columns, then merge back with non-value columns (or full `assign` / `copy` + assign). Row alignment is index-based like the rest of pandas.
  - `copy=False`: return a **view-like** result only where safe; document that for masking, a **copy is usually required** if you must not mutate the original — default `copy=True` uses `df.copy()` then overwrites `value_cols` (simple and predictable).
3. **Validation in `_validate` / method:** Ensure `mask_col` exists, `value_cols` subset of columns, optional dtype check that mask is bool (or cast with `astype(bool)` and warn — pick one consistent behavior).
4. **Optional helper:** `apply_mask_inplace` only if you explicitly want mutation without full frame copy (overwrite `value_cols` in place on `self._obj`); only add if you need it for large frames — otherwise one method keeps surface area small.
5. **Docs:** Fix docstring (remove tab-indented example block or use proper RST); document `mask_col` / `value_cols` / `copy` and that other columns are unchanged.
6. **Out of scope:** Polars path in the same file (there is an unused `import polars` at top — leave as-is or remove in a separate cleanup if desired); spectrogram integration in pyPhoTimeline (that remains ndarray/time bins unless you later pass interval metadata through this accessor).

## Files to touch

- `[dataframe_accessor_helpers.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)`: refactor class hierarchy for `MaskedValidDataFrame`, implement `apply_mask` (+ validation).

## Verification

- No test suite in repo today; verify with a short snippet in a notebook or REPL: bool column, two numeric columns, assert False rows become `pd.NA` and True rows unchanged.

