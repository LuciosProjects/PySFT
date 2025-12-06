
try:
    from ._meta import __version__
except Exception:
    __version__ = "0.0.1"
 
from . import lib # to make lib submodule accessible

__all__ = ["__version__", "lib"]