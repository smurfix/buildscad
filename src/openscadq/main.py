"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

from .eval import Eval
from .peg import Parser
from .work import MainEnv

from typing import TYPE_CHECKING  # isort:skip

if TYPE_CHECKING:
    from pathlib import Path


def process(f: Path, debug: bool = False, **vars):
    """process an OpenSCAD file

    Returns a CadQuery workplane with the result.
    """
    p = Parser(debug=debug, reduce_tree=False)
    tree = p.parse(f.read_text())
    env = MainEnv()
    vars.setdefault("_path", f)
    for k, v in vars.items():
        env[k] = v

    e = Eval(tree, env=env)
    result = e.eval()
    return result
