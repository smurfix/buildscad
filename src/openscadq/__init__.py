"""
OpenSCAD to build123d translator

This package interprets an OpenSCAD model, generating a build123d object
which can be exported to STEP, or processed further with OCCT / Cadquery.
"""
from __future__ import annotations

import contextvars as _ctx

__all__ = ["env", "parse"]

env = _ctx.ContextVar("env")

del _ctx


def parse(*a, **kw):
    global parse
    from .main import parse

    return parse(*a, **kw)
