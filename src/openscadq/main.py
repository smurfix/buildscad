"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

from io import IOBase
from pathlib import Path

from .peg import Parser
from .env import StaticEnv,DynEnv
from .globals import _Fns,_Mods

class _MainEnv(StaticEnv):
    "main environment with global variables"

    def __init__(self):
        super().__init__()

        def collect(cls, d:dict[str,Callable]):
            for k in dir(cls):
                if k[0] == "_":
                    continue
                v = getattr(cls,k)
                if not callable(v):
                    continue
                setattr(v,"_env_", True)
                self.mods
                d[k] = v
        collect(_Mods, self.mods)
        collect(_Fns, self.funcs)


class Env(DynEnv):
    def __init__(self):
        super().__init__(StaticEnv(_MainEnv()))
        self.vars["$fn"] = 999
        self.vars["$fa"] = 0.001
        self.vars["$fs"] = 0.001
        self.vars["$t"] = 0
        self.vars["$children"] = 0
        self.vars["$preview"] = 0

    def set_var(self, name, value):
        self.static.add_var(name, value)

    def set_func(self, name, value):
        self.static.add_func_(name, value)

    def set_mod(self, name, value):
        self.static.add_mod_(name, value)

    def parse(self, data:str):
        p = Parser(debug=False, reduce_tree=False)
        node = p.parse(data)
        self.static.eval(node)

    def run(self):
        return self.union(self.static.work)


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

    env = Env()
    env.parse(r)

    for fn in preload:
        with open(fn) as fd:
            fc = fd.read()
        exec(fc, d)

        # TODO 
        for n, f in d.items():
            if n[0] == "_":
                continue
            if callable(f):
                env.set_func(n,f)
                env.set_mod(n,f)
            else:
                env.set_var(n,f)

    kw.setdefault("_path", f)
    for k, v in kw.items():
        env.set_var(k, v)
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
    return env.union()
