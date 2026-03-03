"""pytest configuration: pre-mock heavy or unavailable external dependencies.

This allows the test suite to run in environments where only core scientific
Python packages (numpy, pandas) and Qt/pylsl are installed, without needing
the full project dependency tree (pyphocorehelpers, phopylslhelper, etc.).

A ``sys.meta_path`` finder is registered at collection time.  It intercepts
import requests for the listed packages and returns lightweight stub modules
that contain:

- A ``__getattr__`` so attribute access on the module always succeeds.
- Proper Python class stubs for known names that are used as base classes of
  Qt widgets (avoiding metaclass conflicts with ``sip.wrappertype``).
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import types
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Packages that are not available in the sandbox environment
# ---------------------------------------------------------------------------
_STUB_PREFIXES = (
    "pyphocorehelpers",
    "phopylslhelper",
    "phopymnehelper",
    "pyoptics",
    "nptyping",
    "pyxdf",
    "vispy",
    "cv2",
    "imageio",
    "awkward",
)

# Names that appear as base classes of QWidget subclasses must be real Python
# classes (not MagicMock), otherwise the sip metaclass cannot be combined.
_KNOWN_MIXIN_NAMES = {
    "PlottingBackendSpecifyingMixin",
    "PlotImageExportableMixin",
    "PlottingBackendType",
    "CrosshairsTracingMixin",
    "TrackOptionsPanelOwningMixin",
    "TrackRenderingMixin",
    "SpecificDockWidgetManipulatingMixin",
    "DynamicDockDisplayAreaContentMixin",
    "DynamicDockDisplayAreaOwningMixin",
    "ExtendedEnum",
}


def _is_stubbed(fullname: str) -> bool:
    return any(
        fullname == p or fullname.startswith(p + ".") for p in _STUB_PREFIXES
    )


class _StubAttr:
    """A stub that can be:
    - used as a Python base class (is a proper type)
    - called as a no-op decorator factory (@stub, @stub(...))
    - used as an instance (attribute access returns another _StubAttr)
    """

    def __init_subclass__(cls, **kwargs):
        pass  # silence subclassing complaints

    def __new__(cls, *args, **kwargs):
        # When used as a base class, Python calls type.__new__ indirectly;
        # but when explicitly instantiated by user code we return a fresh instance.
        return object.__new__(cls)

    def __init__(self, name: str = "_stub"):
        self._name = name

    # Allow direct decoration: @stub_attr
    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not isinstance(args[0], type):
            return args[0]
        # Called as factory: @stub_attr(...)
        def _deco(fn):
            return fn
        return _deco

    def __getattr__(self, name: str):
        return _StubAttr(name)

    def __iter__(self):
        return iter([])

    def __mro_entries__(self, bases):
        # When used as a base class in `class Foo(Visual):`,
        # Python calls __mro_entries__ to resolve the actual MRO.
        # Return an empty tuple to silently skip this "base".
        return ()

    def __repr__(self):
        return f"<_StubAttr '{self._name}'>"


class _StubModule(types.ModuleType):
    """A module stub that returns _StubAttr or real classes on attribute access."""

    def __getattr__(self, name: str):
        if name in _KNOWN_MIXIN_NAMES:
            stub_cls = type(name, (), {})
            object.__setattr__(self, name, stub_cls)
            return stub_cls
        # Return a _StubAttr that works as both a base class AND a decorator
        stub = _StubAttr(name)
        object.__setattr__(self, name, stub)
        return stub


def _make_stub(fullname: str) -> types.ModuleType:
    if fullname in sys.modules:
        return sys.modules[fullname]
    stub = _StubModule(fullname)
    stub.__path__ = []
    stub.__package__ = fullname.rsplit(".", 1)[0] if "." in fullname else fullname
    sys.modules[fullname] = stub
    return stub


class _StubFinder(importlib.abc.MetaPathFinder):
    """Modern (PEP 451) meta-path finder that stubs unavailable packages."""

    def find_spec(self, fullname, path, target=None):
        if not _is_stubbed(fullname):
            return None
        parts = fullname.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            if parent not in sys.modules:
                _make_stub(parent)
        _make_stub(fullname)
        return importlib.machinery.ModuleSpec(
            fullname,
            loader=self,
            is_package=True,
        )

    def create_module(self, spec):
        return sys.modules.get(spec.name)

    def exec_module(self, module):
        pass


_finder = _StubFinder()
if not any(isinstance(f, _StubFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _finder)
