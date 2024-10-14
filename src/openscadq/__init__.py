"""
OpenSCAD to build123d translator

This package interprets an OpenSCAD model, generating a build123d object
which can be exported to STEP, or processed further with OCCT / Cadquery.
"""

import contextvars as _ctx

__all__ = ["env"]

env = _ctx.ContextVar("env")

del _ctx
