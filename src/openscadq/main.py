"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

from io import IOBase
from pathlib import Path

from .peg import Parser
from .env import StaticEnv,DynEnv,SpecialEnv
from .globals import _Fns,_Mods

class _MainEnv(SpecialEnv):
    "main environment with global variables"

    def __init__(self):
        env = StaticEnv()
        super().__init__(env)

        def collect(cls, d:dict[str,Callable]):
            for k in dir(cls):
                if k[0] == "_":
                    continue
                v = getattr(cls,k)
                if not callable(v):
                    continue
                setattr(v,"_env_", True)
                if k[-1] == "_":
                    k=k[:-1]
                d[k] = v
        collect(_Mods, env.mods)
        collect(_Fns, env.funcs)

    def add_var(self, *a, **kw):
        "internal. Forwards to parent."
        self.parent.add_var(*a, **kw)

    def add_func_(self, *a, **kw):
        "internal. Forwards to parent."
        self.parent.add_func_(*a, **kw)

    def add_mod_(self, *a, **kw):
        "internal. Forwards to parent."
        self.parent.add_mod_(*a, **kw)

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


def parse(f: Path | str, /) -> MainEnv:
    """Parse an OpenSCAD file.

    Returns a `MainEnv` object that can be used to build the contents.

    The single positional argument is either the file, or the literal
    string, to interpret as an OpenSCAD file.

    Additional keyword arguments are used as variables variables.
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

    return env


def process(f, /, *fn, **kw):
    """process an OpenSCAD file.

    Returns a build123d object with the result.

    @preload refers to files that preload functions. They are intended to
    be modules or functions that need to be re-implemented, e.g. because
    they call ``hull`` or ``minkowski``.

    Keyword arguments can be used to override variables, function,s or
    modules.
    """
    env = parse(*a, **kw)
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

    for k, v in kw.items():
        if callable(v):
            env.set_func(k,v)
            env.set_mod(k,v)
        else:
            env.set_var(k,v)

    return env.union()
