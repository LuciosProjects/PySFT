
try:
    from ._meta import __version__
except Exception:
    __version__ = "0.0.1"

# Keep package import resilient when optional dependencies for submodules
# are unavailable in lightweight environments.
from . import data # to make data submodule accessible
from . import lib # to make lib submodule accessible

__all__ = ["__version__", "__path__",
           "data", "lib"]