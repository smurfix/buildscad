"""
OpenSCAD to CadQuery translator

This package interprets an OpenSCAD model, generating a CadQuery workplane
which can be exported to STEP.
"""

import contextvars as _ctx

__all__ = ["env"]

env = _ctx.ContextVar("env")

del _ctx
