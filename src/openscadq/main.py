"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

from io import IOBase
from pathlib import Path

from .eval import Eval
from .peg import Parser
from .work import MainEnv


def parse(f: Path | str, debug: bool = False, preload: list[str] = (), **kw):
    """parse an OpenSCAD file

    Returns an environment useable for evaluation(s).

    @preload refers to files that preload functions. They are intended to
    be modules or functions that need to be re-implemented, e.g. because
    they call ``hull`` or ``minkowski``.

    Additional keyword arguments are used as environment variables.
    A warning is printed if there's a conflict.
    """
    if isinstance(f, IOBase):
        r = f.read()
        f.close()
    elif isinstance(f, str) and "\n" in f:
        r = f
    else:
        r = Path(f).read_text()
    p = Parser(debug=debug, reduce_tree=False)
    tree = p.parse(r)
    env = MainEnv()
    ev = Eval(env, debug=debug)
    xx = ev.eval(tree)

    d = {"env": env}

    for fn in preload:
        with open(fn) as fd:
            fc = fd.read()
        exec(fc, d)
        for n, f in d.items():
            if callable(f):
                env[n] = f

    kw.setdefault("_path", f)
    for k, v in kw.items():
        env[k] = v
    return env


def process(*a, **kw):
    """process an OpenSCAD file

    Returns a build123d object with the result.

    @preload refers to files that preload functions. They are intended to
    be modules or functions that need to be re-implemented, e.g. because
    they call ``hull`` or ``minkowski``.

    Additional keyword arguments are used as environment variables.
    A warning is printed if there's a conflict.
    """
    env = parse(*a, **kw)

    result = e.children()
    return result
