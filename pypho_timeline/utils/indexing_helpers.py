"""Pandas DataFrame helper utilities."""

import pandas as pd
from typing import Tuple


class PandasHelpers:
    """Helper class for pandas DataFrame operations."""
    
    @staticmethod
    def empty_df_like(df: pd.DataFrame) -> pd.DataFrame:
        """Create an empty DataFrame with the same columns and dtypes as the input.
        
        Args:
            df: DataFrame to use as template
            
        Returns:
            Empty DataFrame with same structure
        """
        return df.iloc[0:0].copy()
    
    @staticmethod
    def get_df_row_changes(potentially_updated_df: pd.DataFrame, prev_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compare two DataFrames and identify added, unchanged, and removed rows.
        
        Args:
            potentially_updated_df: The new/updated DataFrame
            prev_df: The previous DataFrame to compare against
            
        Returns:
            Tuple of (added_rows, same_rows, removed_rows) DataFrames
        """
        # If previous DataFrame is empty, all rows in updated are new
        if len(prev_df) == 0:
            return potentially_updated_df.copy(), pd.DataFrame(), pd.DataFrame()
        
        # If updated DataFrame is empty, all rows in previous are removed
        if len(potentially_updated_df) == 0:
            return pd.DataFrame(), pd.DataFrame(), prev_df.copy()
        
        # Simple approach: use index-based comparison if indices are meaningful
        # Otherwise, use a merge-based approach
        if potentially_updated_df.index.equals(prev_df.index):
            # Same indices - compare row by row
            common_idx = potentially_updated_df.index.intersection(prev_df.index)
            added_idx = potentially_updated_df.index.difference(prev_df.index)
            removed_idx = prev_df.index.difference(potentially_updated_df.index)
            
            added_rows = potentially_updated_df.loc[added_idx] if len(added_idx) > 0 else pd.DataFrame()
            removed_rows = prev_df.loc[removed_idx] if len(removed_idx) > 0 else pd.DataFrame()
            
            # For same rows, check if content actually changed
            same_idx = []
            for idx in common_idx:
                if idx in potentially_updated_df.index and idx in prev_df.index:
                    row_updated = potentially_updated_df.loc[[idx]]
                    row_prev = prev_df.loc[[idx]]
                    # Simple comparison - check if values are equal
                    try:
                        if row_updated.equals(row_prev):
                            same_idx.append(idx)
                    except:
                        # If comparison fails, assume changed
                        pass
            
            same_rows = potentially_updated_df.loc[same_idx] if len(same_idx) > 0 else pd.DataFrame()
        else:
            # Different indices - use merge approach
            # This is a simplified version - may need refinement based on actual use cases
            added_rows = potentially_updated_df.copy()
            removed_rows = prev_df.copy()
            same_rows = pd.DataFrame()
        
        return added_rows, same_rows, removed_rows

