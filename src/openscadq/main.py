"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

from .eval import Eval
from .peg import Parser
from .work import MainEnv
from pathlib import Path


def process(f: Path|str, debug: bool = False, preload: list[str] = (), **vars):
    """process an OpenSCAD file

    Returns a build123d object with the result.

    @preload refers to files that preload functions. They are intended to
    be modules or functions that need to be re-implemented, e.g. because
    they call ``hull`` or ``minkowski``.

    Additional keyword arguments are used as environment variables.
    A warning is printed if there's a conflict.
    """
    p = Parser(debug=debug, reduce_tree=False)
    tree = p.parse((f if isinstance(f,str) and "\n" in f else Path(f).read_text()))
    env = MainEnv()
    d = {'env': env}

    for fn in preload:
        with open(fn,"r") as fd:
            fc = fd.read()
        exec(fc,d)
        for n,f in d.items():
            if callable(f):
                env[n] = f

    vars.setdefault("_path", f)
    for k, v in vars.items():
        env[k] = v

    e = Eval(tree, env=env)
    result = e.eval()
    return result
