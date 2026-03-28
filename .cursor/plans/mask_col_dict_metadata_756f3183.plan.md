---
name: mask_col dict metadata
overview: "Replace `attrs['mask_col_names']: List[str]` with `attrs['mask_col_to_value_cols']: Dict[str, List[str]]` on `MaskedValidDataFrameAccessor`, rewrite `get_masked` / `add_masking_column` accordingly, and optionally migrate legacy attrs for existing DataFrames."
todos:
  - id: property-attrs
    content: Add mask_col_to_value_cols property + default {}; legacy migration from mask_col_names in getter
    status: completed
  - id: init-getmasked
    content: __init__ use empty mapping; rewrite get_masked loop per dict entry with validation
    status: completed
  - id: add-masking
    content: "add_masking_column: assign dict[mask_col] = list(value_cols); call get_masked"
    status: completed
  - id: docs
    content: Update class/method docstrings (dict semantics, remove apply_mask references)
    status: completed
isProject: false
---

# Dict-based mask metadata for `MaskedValidDataFrameAccessor`

## Context

Current implementation in `[PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)`:

- Stores `mask_col_names` (list) in `df.attrs`.
- `[get_masked](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/helpers/dataframe_accessor_helpers.py)` ANDs **all** mask columns into one boolean series, then masks **every** column except the mask columns (global application).

The new model: `**mask_col_to_value_cols: Dict[str, List[str]]`** — each mask column only drives masking for its listed value columns.

**Semantics:** For each `(mask_col, value_cols)` entry, apply `df[value_cols].where(mask_series, pd.NA)` on the working frame. Processing entries **in sequence** yields the same effect as AND-ing masks for any column that appears under multiple keys (NA if any governing mask is False).

**No downstream API uses `mask_col_names` directly** (grep: only this file + notebooks). `[pypho_timeline/rendering/helpers/normalization.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/helpers/normalization.py)` imports `MaskedValidDataFrameAccessor` but does not reference the property.

## Implementation steps

1. **Attr key and property**
  - Add a property (e.g. `mask_col_to_value_cols`) typed `Dict[str, List[str]]` reading/writing `self._obj.attrs['mask_col_to_value_cols']`.  
  - Default to `{}` when missing (ensure `attrs` dict exists, same pattern as today).
2. **Legacy migration (recommended)**
  - In the getter, if `'mask_col_to_value_cols'` is absent but `'mask_col_names'` is a non-empty list, build an equivalent dict **using the current frame’s columns**:  
   `value_cols = [c for c in df.columns if c not in set(old_mask_names)]`, then `{m: value_cols.copy() for m in old_mask_names}`.  
   This reproduces the old “one global AND mask on all non-mask columns” behavior for persisted/old DataFrames.
3. `**__init__`**
  - Stop initializing with `mask_col_names=['is_valid']` (that pre-populates metadata unrelated to actual columns).  
  - Initialize metadata with `mask_col_to_value_cols={}` via `adding_or_updating_metadata` (or only ensure empty dict on first access—minimal touch).
4. `**get_masked(copy=...)`**
  - If the mapping is empty: return `df.copy(deep=copy)` unchanged (same net effect as today’s empty list + all-True mask).  
  - Otherwise: `out = df.copy(deep=copy)`; for each `(mask_col, value_cols)` in **deterministic key order** (e.g. `sorted` for reproducibility):  
    - Validate `mask_col` and all `value_cols` exist; reject if `mask_col` appears in `value_cols`.  
    - Reuse the existing per-column mask construction (`boolean` / `fillna(False)` pattern from lines 136–139).  
    - `out[list(value_cols)] = out[list(value_cols)].where(mask, pd.NA)`.
  - Do **not** use a single global `value_cols_list` derived from “all columns minus mask columns”; only the lists in the dict define what gets masked.
5. `**add_masking_column(mask_col, value_cols, *, copy=...)`**
  - Validate as today.  
  - **Set** `self.mask_col_to_value_cols[mask_col] = list(value_cols)` (replaces prior list for that key so repeat calls update behavior—fixes the old quirk where a second call with the same `mask_col` ignored new `value_cols`).  
  - Return `self.get_masked(copy=copy)`.
6. **Docstrings**
  - Update class docstring and examples to describe the dict and remove references to non-existent `apply_mask` (use `add_masking_column` / `get_masked`).  
  - Note `attrs` key name for pickling/round-trip expectations.

## Optional cleanup (only if you want it in the same PR)

- Remove unused `MaskValidDataFrameAccessor` import from `[normalization.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/helpers/normalization.py)` if still unused after edit (user preference: minimal edits—skip if unrelated).

## Testing suggestion

- Small inline or pytest: empty dict → unchanged; one mask + subset of columns → only those columns get NA; two masks with overlapping value column → behaves like AND; legacy `mask_col_names` only → migration path matches old global masking.

