"""datapipe — portable collect→clean→cross-check→update engine.

The deterministic core (clean/cross-check/update + credibility tiering) is
stdlib-only and runs on any platform. The search/fan-out step is platform-
specific and lives outside this package.
"""
from . import core, tierlib  # noqa: F401

__version__ = "0.1.0"
