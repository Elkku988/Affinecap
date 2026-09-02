"""Runtime affine-style capabilities for Python."""

from ._core import (
    Capability,
    CapabilityConsumedError,
    CapabilityError,
    CapabilityIntegrityError,
    CapabilityProcessError,
    LineageEntry,
    issue,
)

__all__ = [
    "Capability",
    "CapabilityConsumedError",
    "CapabilityError",
    "CapabilityIntegrityError",
    "CapabilityProcessError",
    "LineageEntry",
    "issue",
]

__version__ = "0.1.0"
