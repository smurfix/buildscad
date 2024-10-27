"""
OpenSCAD to build123d translator

This package interprets an OpenSCAD model, generating a build123d object
which can be exported to STEP, or processed further with OCCT / Cadquery.
"""
from __future__ import annotations

import contextvars as _ctx

__all__ = ["env", "parse", "process", "Assertion"]

env = _ctx.ContextVar("env")

del _ctx

class Assertion(AssertionError):
    """The interpreted code called a failing ``assert`` function."""
    pass

from .main import parse, process

