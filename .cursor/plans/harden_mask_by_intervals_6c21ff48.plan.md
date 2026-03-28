---
name: Harden mask_by_intervals
overview: "Complete and correct `MaskedValidDataFrameAccessor.mask_by_intervals`: implement dropping an existing mask column, validate inputs, fix pandas accessor semantics (return value vs silent reassignment), preserve index through Polars round-trip where possible, and remove redundant imports."
todos:
  - id: drop-col-validate
    content: Implement drop of bool_mask_column_name when present; validate time/interval columns; handle empty intervals
    status: completed
  - id: polars-roundtrip-index
    content: Polars from_pandas/to_pandas with index preservation; remove inner import; return out only
    status: completed
  - id: docstring-api
    content: Document assign-return pattern and parameter semantics in docstring
    status: completed
isProject: false
---

# Harden `[mask_by_intervals](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)`

## Problems in current code (lines 121–148)

1. **Comment vs behavior:** Line 130 says to drop `bool_mask_column_name` if present, but nothing does. If that column already exists, the Polars `join` / schema can conflict or duplicate names.
2. `**self._obj = df.to_pandas()`:** For pandas [register_dataframe_accessor](https://pandas.pydata.org/docs/development/extending.html), `self._obj` is the caller’s DataFrame reference. Reassigning `self._obj` to a **new** frame does **not** replace the object the user holds; only the **return value** reliably delivers the result. The reassignment is misleading and should be removed in favor of `out = ...; return out` (same pattern as `apply_mask`, which does not overwrite `self._obj`).
3. **Redundant import:** `polars` is already imported at module top ([line 9](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)); delete the inner `import polars as pl`.
4. **Index round-trip:** Default `pl.from_pandas` / `DataFrame.to_pandas()` can drop or alter non-trivial indexes. Use Polars’ documented `include_index` / equivalent for your pinned version (`[polars[all]>=1.39.3](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/pyproject.toml)`) so `detailed_eeg_df` row identity matches after conversion, or document that caller must `reset_index` first. Prefer the API that preserves index for typical EEG/motion frames.
5. **Validation:** Assert `time_col_name` exists on `self._obj`, interval columns exist on `mask_bad_intervals_df`, and optionally handle empty interval frame (all `False` for the new column without error).

## Implementation outline

- At the start of `mask_by_intervals`, build a working pandas base: if `bool_mask_column_name` is in `self._obj.columns`, `drop(columns=[bool_mask_column_name], errors="ignore")` (operate on a **copy** if you want non-mutating behavior on the input frame before Polars; simplest is copy-once then full pipeline so the original `df` is never partially mutated).
- Convert with index preservation (per Polars 1.39 docs), run the existing lazy pipeline (`cross` join + interval filter + `unique` + left join + `fill_null(False)`), convert back with index restored.
- Add return type `-> pd.DataFrame`, keyword-only optional args if you want: `closed` / half-open interval (future).
- Docstring: state explicitly that callers should assign the return value, e.g. `df = df.masked_df.mask_by_intervals(...)`.

## Files

- Single file: `[PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)`

## Verification

- Quick REPL: small `df` with `t`, interval df with one row, expect `is_bad_motion` True only in range; repeat with pre-existing `is_bad_motion` column and confirm no duplicate/error and correct recomputation.
- If index is named or non-RangeIndex, confirm it matches before/after.

