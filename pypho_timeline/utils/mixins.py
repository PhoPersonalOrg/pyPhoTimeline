"""Mixin classes for tuple unpacking and dynamic instance conformance."""

from typing import List, Optional


class UnpackableMixin:
    """Mixin that allows attrs classes to be unpacked like tuples.
    
    Classes using this mixin should implement `UnpackableMixin_unpacking_includes()`
    to specify which attributes should be included when unpacking.
    """
    
    def __iter__(self):
        """Make the class iterable for tuple unpacking."""
        includes = self.UnpackableMixin_unpacking_includes()
        if includes is None:
            # If no includes specified, try to get all attrs fields
            if hasattr(self, '__attrs_attrs__'):
                includes = [attr.name for attr in self.__attrs_attrs__]
            else:
                includes = []
        
        for attr in includes:
            if hasattr(attr, 'name'):
                # It's an attrs Attribute object - get the name and then the value
                yield getattr(self, attr.name)
            elif isinstance(attr, str):
                # It's an attribute name string
                yield getattr(self, attr)
            else:
                # It's already a value (shouldn't happen with attrs, but handle it)
                yield attr
    
    def UnpackableMixin_unpacking_includes(self) -> Optional[List]:
        """Items to be included (allowlist) from unpacking.
        
        Must be overridden by subclasses to specify which attributes to include.
        """
        return None


class BaseDynamicInstanceConformingMixin:
    """Base mixin for dynamic instance conformance.
    
    This is a minimal stub replacement for neuropy's BaseDynamicInstanceConformingMixin.
    If more functionality is needed, it should be added here.
    """
    pass

