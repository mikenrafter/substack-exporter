"""Test-only fallback for the local credentials module."""

import sys
from types import ModuleType


if "config" not in sys.modules:
    try:
        __import__("config")
    except ModuleNotFoundError:
        config = ModuleType("config")
        config.EMAIL = ""
        config.PASSWORD = ""
        sys.modules["config"] = config
