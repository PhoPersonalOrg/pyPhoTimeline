"""RectangleRenderTupleHelpers - Helper class for copying and serializing interval rectangle data.

Refactored from pyphoplacecellanalysis for use in pypho_timeline.
"""
from typing import List, Tuple, Optional
import pyqtgraph as pg
from qtpy import QtGui


class RectangleRenderTupleHelpers:
    """Class for use in copying, serializing, etc the list of tuples used by IntervalRectsItem.

    Refactored out of `pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.GraphicsObjects.IntervalRectsItem.IntervalRectsItem` on 2022-12-05 

    Usage:
        from pypho_timeline.rendering.graphics.rectangle_helpers import RectangleRenderTupleHelpers
        
    Known Usages:
        Used in `IntervalRectsItem` to copy themselves

        # Copy Constructors:
        def __copy__(self):
            independent_data_copy = RectangleRenderTupleHelpers.copy_data(self.data)
            return IntervalRectsItem(independent_data_copy)
        
        def __deepcopy__(self, memo):
            independent_data_copy = RectangleRenderTupleHelpers.copy_data(self.data)
            return IntervalRectsItem(independent_data_copy)
    """
    
    _color_process_fn = lambda a_color: pg.colorStr(a_color)  # a_pen.color()

    @staticmethod
    def QPen_to_dict(a_pen):
        return {'color': RectangleRenderTupleHelpers._color_process_fn(a_pen.color()), 'width': a_pen.widthF()}

    @staticmethod
    def QBrush_to_dict(a_brush):
        return {'color': RectangleRenderTupleHelpers._color_process_fn(a_brush.color())}

    @classmethod
    def get_serialized_data(cls, tuples_data):
        """Converts the list of (float, float, float, float, QPen, QBrush) tuples or IntervalRectsItemData objects into a serialized format for serialization. 
        
        Handles both:
        - Tuples: (start_t, series_vertical_offset, duration_t, series_height, pen, brush) [+ optional label]
        - IntervalRectsItemData objects: with optional label field
        
        Returns serialized format: (start_t, series_vertical_offset, duration_t, series_height, pen_dict, brush_dict, label, is_interval_data)
        """            
        if not tuples_data:
            return []
        
        # Check if first item is IntervalRectsItemData (lazy check to avoid circular dependency)
        first_item = tuples_data[0]
        is_interval_data = hasattr(first_item, '__attrs_attrs__') and hasattr(first_item, 'start_t')
        
        result = []
        for item in tuples_data:
            if is_interval_data:
                # Handle IntervalRectsItemData object
                start_t = item.start_t
                series_vertical_offset = item.series_vertical_offset
                duration_t = item.duration_t
                series_height = item.series_height
                pen = item.pen
                brush = item.brush
                label = getattr(item, 'label', None)  # Optional label field
            else:
                # Handle tuple - unpack first 6 required fields
                start_t, series_vertical_offset, duration_t, series_height, pen, brush = item[:6]
                label = item[6] if len(item) > 6 else None  # Optional 7th field (label)
            
            # Serialize pen and brush to dicts
            serialized_item = (start_t, series_vertical_offset, duration_t, series_height, cls.QPen_to_dict(pen), cls.QBrush_to_dict(brush), label, is_interval_data)
            result.append(serialized_item)
        return result

    @classmethod
    def get_deserialized_data(cls, seralized_tuples_data):
        """Converts the serialized data back to the original format (tuples or IntervalRectsItemData objects)
        
        Inverse operation of .get_serialized_data(...).
        
        Handles both old format (6-7 elements) and new format (8 elements with type info).
        
        Usage:
            seralized_tuples_data = RectangleRenderTupleHelpers.get_serialized_data(tuples_data)
            tuples_data = RectangleRenderTupleHelpers.get_deserialized_data(seralized_tuples_data)
        """        
        if not seralized_tuples_data:
            return []
        
        # Check format: new format has 8 elements (includes is_interval_data flag)
        first_item = seralized_tuples_data[0]
        if len(first_item) == 8:
            # New format: includes is_interval_data flag
            use_objects = first_item[7]
        else:
            # Old format: assume tuples for backward compatibility
            use_objects = False
        
        # Lazy import to avoid circular dependency
        if use_objects:
            try:
                from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItemData
            except ImportError:
                use_objects = False
        
        result = []
        for item in seralized_tuples_data:
            if len(item) == 8:
                # New format with type info
                start_t, series_vertical_offset, duration_t, series_height, pen_dict, brush_dict, label, is_interval_data = item
            elif len(item) == 7:
                # Old format: 7 elements (with label)
                start_t, series_vertical_offset, duration_t, series_height, pen_dict, brush_dict, label = item
            else:
                # Old format: 6 elements (no label)
                start_t, series_vertical_offset, duration_t, series_height, pen_dict, brush_dict = item
                label = None
            
            # Reconstruct pen and brush from dicts
            # pen_dict: {'color': str, 'width': float}
            # brush_dict: {'color': str}
            pen = pg.mkPen(pen_dict['color'], width=pen_dict.get('width', 1))
            brush = pg.mkBrush(brush_dict['color'])
            
            if use_objects:
                # Return IntervalRectsItemData objects
                if label is not None:
                    result.append(IntervalRectsItemData(start_t, series_vertical_offset, duration_t, series_height, pen, brush, label))
                else:
                    result.append(IntervalRectsItemData(start_t, series_vertical_offset, duration_t, series_height, pen, brush))
            else:
                # Return tuples (backward compatibility)
                if label is not None:
                    result.append((start_t, series_vertical_offset, duration_t, series_height, pen, brush, label))
                else:
                    result.append((start_t, series_vertical_offset, duration_t, series_height, pen, brush))
        return result

    @classmethod
    def copy_data(cls, tuples_data):
        """Copy data by serializing and deserializing (creates independent copy)."""
        seralized_tuples_data = cls.get_serialized_data(tuples_data).copy()
        return cls.get_deserialized_data(seralized_tuples_data)

