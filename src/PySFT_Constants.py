"""
PySFT_Constants
----------------

Centralized constants for the PySFT project.

This module defines immutable values used across the codebase to avoid magic
numbers/strings, improve readability, and enable consistent configuration.
Typical contents include:
- Application-wide string literals (e.g., environment keys, resource names)
- Default configuration values (e.g., timeouts, buffer sizes)
- Numeric limits and thresholds (e.g., retries, max items)
- Standardized file extensions, MIME types, and paths
- Enum-like string constants for modes, statuses, and event types

Import this module wherever shared constants are needed to keep values
declarative, discoverable, and maintainable.
"""

# Application environment keys
PYSFT_VERSION = "0.0.1"
