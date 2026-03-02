"""ReprPrintableItemMixin - embedded from pyPhoPlaceCellAnalysis for use in pypho_timeline."""
from typing import List


class ReprPrintableItemMixin:
    """Implementors provide a better repr than the default Qt widget one that shows the class name and memory address."""

    def __repr__(self):
        class_parts: List[str] = str(self.__class__).strip("<class").strip(">").strip(" ").strip("'").split(".")
        class_name: str = class_parts[-1]
        out_str: str = f"{class_name}"
        out_str_list: List[str] = []
        try:
            view_range_str = f"viewRange: [[xmin, xmax], [ymin, ymax]]: {self.viewRange()}"
            out_str_list.append(view_range_str)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass
        except Exception:
            raise
        if len(out_str_list) > 0:
            out_str = f"{out_str}[" + ", ".join(out_str_list) + "]"
        return out_str
