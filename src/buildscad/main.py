"""
Main wrapper to process OpenSCAD files
"""
from __future__ import annotations

import sys
from io import IOBase
from pathlib import Path
from contextlib import contextmanager, nullcontext
from itertools import chain

from .peg import Parser
from .env import StaticEnv,DynEnv,SpecialEnv
from .globals import _Fns,_Mods
from . import main_env

from build123d import Shape, Axis

class _MainEnv(SpecialEnv):
    "main environment with global variables"

    # We stack environments.
    # Main redirects everything that the parser adds to its first parent.
    # The second, toplevel parent contains the built-in globals.
    # This way overrides end up in different environments and thus
    # don't generate warnings when added.

    def __init__(self):
        env = StaticEnv()
        super().__init__(StaticEnv(env))

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
        self.parent.add_var(*a, _env=self, **kw)

    def add_func(self, *a, **kw):
        super().add_func(*a, _env=self, **kw)

    def add_func_(self, *a, **kw):
        "internal. Forwards to parent."
        self.parent.add_func_(*a, **kw)

#   def add_mod(self, *a, **kw):
#       super().add_mod(*a, _env=self, **kw)

    def add_mod_(self, *a, **kw):
        "internal. Forwards to parent."
        self.parent.add_mod_(*a, **kw)

class Env(DynEnv):
    """
    This class supplies the top-level execution environment for BuildSCAD.
    """
    def __init__(self):
        super().__init__(_MainEnv())
        self.vars["$fn"] = 999
        self.vars["$fa"] = 0.001
        self.vars["$fs"] = 0.001
        self.vars["$t"] = 0
        self.vars["$children"] = 0
        self.vars["$preview"] = False
        self.vars["$trace"] = False
        self._tcache = {}
        self._tnext = 1

    def add_var(self, name, value:int|float|str):
        """
        Add a top-level variable.

        Warns if the variable already exists.
        """
        if name[0] == "$":
            raise RuntimeError("Use 'set_var' for dynamic variables")
        else:
            self.static.add_var(name, value)

    def add_func(self, name: str, value: Callable):
        """
        Add a top-level function.

        Warns if the function already exists.
        """
        self.static.add_func_(name, value)

    def add_mod(self, name: str, value: int|float|str):
        """
        Add a top-level module.

        Warns if the module already exists.
        """
        self.static.add_mod_(name, value)

    def set_var(self, name: str, value: int|float|str):
        """
        Update a top-level variable.

        This method doesn't complain if the variable already exists.
        You should use `add_var` instead, if possible.
        """
        if name[0] == "$":
            self.vars[name] = value
        else:
            self.static.vars[name] = value

    def set_func(self, name, value: Callable):
        """
        Update a top-level function.

        This method doesn't complain if the function already exists.
        You should use `add_func` instead, if possible.
        """
        self.static.funcs[name] = value

    def set_mod(self, name, value: Callable):
        """
        Update a top-level module.

        This method doesn't complain if the module already exists.
        You should use `add_mod` instead, if possible.
        """
        self.static._mods[name] = value

    def parse(self, data:str):
        p = Parser(debug=False, reduce_tree=False)
        node = p.parse(data)
        self.static.eval(node)

    def run(self):
        return self.union(self.static.work)

    @contextmanager
    def tracing(self, fn:Path|None=None):
        token = main_env.set(self)
        try:
            self.vars["$trace"] = True
            with nullcontext(sys.stdout) if fn is None else fn.open("w") as self._trace:
                yield
        finally:
            main_env.reset(token)
            self.vars["$trace"] = False
            self._trace = None
            self._tcache = {}

    def trace_(self, a, kw):
        def vn(obj):
            if isinstance(obj,Axis):
                if obj == Axis.X:
                    return "Axis.X"
                if obj == Axis.Y:
                    return "Axis.Y"
                if obj == Axis.Z:
                    return "Axis.Z"
                oid = id(obj)
                if (tn := self._tcache.get(oid, None)) is None:
                    tn,self._tnext = self._tnext, self._tnext+1
                    self._tcache[oid] = tn,obj
                    print(f"o_{tn} = Axis{obj !r}")
                return f"o_{tn}"

            if isinstance(obj,Shape):
                oid = id(obj)
                if (tn := self._tcache.get(oid, None)) is None:
                    tn,self._tnext = self._tnext, self._tnext+1
                    self._tcache[oid] = tn,obj
                else:
                    tn = tn[0]
                return f"o_{tn}"
            return repr(obj)

        res,op,*a = a
        rs = f"{vn(res)} = "
        if op == "_add":
            print(f"{rs}{' + '.join(vn(x) for x in a)}")
            return
        if op == "_inter":
            print(f"{rs}{' & '.join(vn(x) for x in a)}")
            return
        if op == "_diff":
            print(f"{rs}{' & '.join(vn(x) for x in a)}")
            return
        obj = kw.pop("_obj", None)
        if obj is not None:
            rs += f"{vn(obj)}."
        rt = (vn(x) for x in a)
        if kw:
            rt = chain(rt, (f"{k}={vn(v)}" for k,v in kw.items()))
        print(f"{rs}{op}({', '.join(rt)})")


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


def process(f, /, preload=(), **kw) -> Env:
    """process an OpenSCAD file.

    Returns a build123d object with the result.

    @preload refers to files that preload functions. They are intended to
    be modules or functions that need to be re-implemented, e.g. because
    they call ``hull`` or ``minkowski``.

    Keyword arguments can be used to override variables, function,s or
    modules.

    Call the `build` method on the result to get (a composite of) the top-level object.
    """
    env = parse(f)
    for fn in preload:
        with open(fn) as fd:
            fc = fd.read()
        d={}
        exec(fc, d)

        # TODO 
        for n, f in d.items():
            if n[0] == "_" and not isinstance(f,(int,float)):
                continue
            if callable(f):
                env.static.set_func(n,f)
                env.static.set_mod(n,f)
            else:
                env.static.set_var(n,f)

    for k, v in kw.items():
        if callable(v):
            env.set_func(k,v)
            env.set_mod(k,v)
        else:
            env.set_var(k,v)

    return env
