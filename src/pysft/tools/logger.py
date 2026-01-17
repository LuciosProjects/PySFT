"""
Centralized logging configuration for PySFT.
Enhanced for HTTP API usage with request tracking and log rotation.
"""

import logging
import os
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
import contextvars

import pysft.core.constants as const

# ---- Configuration from environment ----
LOG_LEVEL = os.getenv("PYSFT_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("PYSFT_LOG_FILE", None)
LOG_FORMAT = os.getenv(
    "PYSFT_LOG_FORMAT",
    "%(asctime)s | %(name)s | %(levelname)-8s | [%(request_id)s] | %(message)s"
)

# ---- Request ID tracking (for HTTP APIs) ----
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='N/A')

class RequestIdFilter(logging.Filter):
    """Add request ID to all log records."""
    def filter(self, record):
        record.request_id = _request_id.get()
        return True

def set_request_id(request_id: str) -> None:
    """
    Set the request ID for the current async context.
    Call this in your HTTP middleware or request handler.
    
    Usage (FastAPI):
        @app.middleware("http")
        async def add_request_id(request: Request, call_next):
            request_id = str(uuid.uuid4())
            pysft.tools.logger.set_request_id(request_id)
            response = await call_next(request)
            return response
    """
    _request_id.set(request_id)

# ---- Module-level logger cache ----
_LOGGERS: dict[str, logging.Logger] = {}

def _setup_root_logger() -> logging.Logger:
    """Configure the root logger with console and optional file handlers."""
    root = logging.getLogger("pysft")
    
    # Avoid duplicate handlers
    if root.handlers:
        return root
    
    root.setLevel(LOG_LEVEL)
    
    # Add request ID filter to all handlers
    request_filter = RequestIdFilter()
    
    # ---- Console Handler ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(request_filter)
    root.addHandler(console_handler)
    
    # ---- File Handler (with rotation for production) ----
    if LOG_FILE:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # RotatingFileHandler: rotate when file exceeds 10MB, keep 5 backups
        file_handler = RotatingFileHandler(
            log_path,
            mode="a",
            maxBytes=10 * const.ONE_MB,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(console_formatter)
        file_handler.addFilter(request_filter)
        root.addHandler(file_handler)
    
    return root

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for a module.
    
    Args:
        name: Module name (typically __name__). If None, returns root logger.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    if name is None:
        return _setup_root_logger()
    
    if name not in _LOGGERS:
        root = _setup_root_logger()
        _LOGGERS[name] = root.getChild(name.split(".")[-1])
    
    return _LOGGERS[name]

def set_log_level(level: str) -> None:
    """Dynamically change log level at runtime."""
    level = level.upper()
    root = logging.getLogger("pysft")
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)