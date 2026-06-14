"""Deprecated compatibility shim.

``qtwebplot`` has moved under ``qtviz.backends.webengine``. Importing this
package (or any of its old submodules) transparently redirects to the new
location and emits a :class:`DeprecationWarning`. The shim will be removed in a
future release (roadmap Phase 6).
"""

from __future__ import annotations

import importlib
import sys
import warnings
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

_OLD = "qtwebplot"
_NEW = "qtviz.backends.webengine"


class _RedirectLoader(Loader):
    """Resolve an old ``qtwebplot.*`` name to the already-imported new module so
    both names share one module object (no duplicate execution)."""

    def __init__(self, new_name: str) -> None:
        self._new_name = new_name

    def create_module(self, spec: ModuleSpec):
        module = importlib.import_module(self._new_name)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module) -> None:  # already executed under its real name
        pass


class _RedirectFinder(MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == _OLD or fullname.startswith(_OLD + "."):
            new_name = _NEW + fullname[len(_OLD):]
            return ModuleSpec(fullname, _RedirectLoader(new_name))
        return None


if not any(isinstance(f, _RedirectFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _RedirectFinder())

warnings.warn(
    "'qtwebplot' has moved to 'qtviz.backends.webengine'. Update your imports; "
    "this compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Make the top-level name an alias of the new package so attribute access
# (`from qtwebplot import WebBridgeView`) resolves immediately.
sys.modules[__name__] = importlib.import_module(_NEW)
