"""
This module contains the environment container for interpreting OpenSCAD
functions and whatnot.

The environment also contains all static functions defined for OpenSCAD,
i.e. those that do the actual work, which is why this module is named "work".
"""
from __future__ import annotations

import math
import warnings
from contextlib import contextmanager

from .vars import Vars

import cadquery as cq


class EnvCall:
    """Environment-specific function call."""

    def __init__(self, fn, env):
        self.fn = fn
        self.env = env
        self.is_new = False

    def __call__(self, *a, **k):  # noqa:D102  # XXX
        vars = self.env.vars_dyn if self.fn[0] == "$" else self.env.vars
        return vars[self.fn](*a, _env=self.env, **k)


class Env:
    """Execution environment for interpreting OpenSCAD"""

    current_call = None
    eval = None

    def __init__(
        self,
        parent: Env | Vars,
        name: str | None = None,
        init: dict | None = None,
        vars_dyn: Vars = None,
    ):
        if isinstance(parent, Env):
            self.parent = parent
            self.vars = parent.vars.child(name, init=init)
            self.vars_dyn = vars_dyn if vars_dyn is not None else parent.vars_dyn.child(name, init=init)
        else:
            if init is not None:
                raise ValueError("invalid")
            self.vars = parent
            self.vars_dyn = vars_dyn if vars_dyn is not None else parent
            self.parent = parent

    def __getitem__(self, k):
        if k == "$children":
            return len(self.vars["_e_children"])
        try:
            fn = (self.vars_dyn if k[0] == "$" else self.vars)[k]
        except KeyError:
            if k == "import":
                k = "import_"
            return getattr(self, k)
        else:
            if isinstance(fn, EnvCall):
                pass
            elif callable(fn):
                fn = EnvCall(k, env=self)
            return fn

    def __setitem__(self, k, v):
        (self.vars_dyn if k[0] == "$" else self.vars)[k] = v

    def inject_vars(self, env):
        """inject the result of "use" or "import" into the environment"""
        self.vars.inject(env.vars)
        self.vars_dyn.inject(env.vars_dyn)

    def set_cc(self, k, v):
        "set variables for a possibly-wrapped call"
        if self.current_call is None:
            self.vars[k] = v
        else:
            cc = self.current_call
            if not cc.is_new:
                cc.is_new = True
                env = Env(name=cc.fn, parent=cc.env)
                self.current_call = cc = EnvCall(cc.fn, env)
            cc.env.vars[k] = v

    @contextmanager
    def cc(self, fn):
        "Call wrapper"
        if isinstance(fn, EnvCall):
            self.current_call, cc = fn, self.current_call
            try:
                yield self
            finally:
                self.current_call = cc
        else:
            yield self

    PI = math.pi
    undef = None

    def version(self):  # noqa:D102
        return "0.1.0"

    def echo(self, *a, **k):  # noqa:D102
        class DE:
            def __repr__(self):
                return ", ".join(f"{k} = {v !r}" for k, v in k.items())

        if k:
            a = a + (DE(),)
        print("ECHO:", ", ".join(repr(x) for x in a))

    def sphere(self, r=None, d=None):  # noqa:D102
        if r is None:
            if d is None:
                r = 1
            else:
                r = d / 2
        elif d is not None:
            warnings.warn("sphere: parameters are ambiguous")

        return cq.Workplane("XY").sphere(r)

    def cube(self, size=1, center=False):  # noqa:D102
        if isinstance(size, (int, float)):
            x, y, z = size, size, size
        else:
            x, y, z = size
        res = cq.Workplane("XY").box(x, y, z)
        if not center:
            res = res.translate((x / 2, y / 2, z / 2))
        return res

    def cylinder(self, h=1, r1=None, r2=None, r=None, d=None, d1=None, d2=None, center=False):  # noqa:D102
        if (
            (
                (r1 is not None)
                + (r2 is not None)
                + (d1 is not None)
                + (d2 is not None)
                + 2 * (r is not None)
                + 2 * (d is not None)
            )
            > 2
            or (r1 is not None and d1 is not None)
            or (r2 is not None and d2 is not None)
        ):
            warnings.warn("cylinder: parameters are ambiguous")

        if r is not None:
            r1 = r2 = r
        if d is not None:
            r1 = r2 = d / 2
        if d1 is not None:
            r1 = d1 / 2
        if d2 is not None:
            r2 = d1 / 2

        if r1 is None:
            r1 = 1
        if r2 is None:
            r2 = 1

        res = cq.Workplane("XY").circle(r1)
        if r1 == r2:
            res = res.extrude(h)
        else:
            res = res.workplane(offset=h).circle(r2).loft(combine=True)
        if center:
            res = res.translate([0, 0, -h / 2])
        return res

    def translate(self, v):  # noqa:D102
        ch = self._children()
        if ch is None:
            return None
        return ch.translate(v)

    def rotate(self, a=None, v=None):  # noqa:D102
        ch = self._children()
        if ch is None:
            return None
        if v is not None:
            return ch.rotate((0, 0, 0), v, a)
        elif isinstance(a, (float, int)):
            return ch.rotate((0, 0, 0), (0, 0, 1), a)
        else:
            if a[0]:
                ch = ch.rotate((0, 0, 0), (1, 0, 0), a[0])
            if a[1]:
                ch = ch.rotate((0, 0, 0), (0, 1, 0), a[1])
            if a[2]:
                ch = ch.rotate((0, 0, 0), (0, 0, 1), a[2])
            return ch

    def difference(self):  # noqa:D102
        ch = self._children()
        if ch is None:
            return None
        if len(ch.objects) == 1:
            return ch

        ws = cq.Workplane("XY")
        ws.add(ch.objects[0])

        for obj in ch.objects[1:]:
            ws = ws.cut(obj, clean=False, tol=0.001)
        return ws.clean()

    def union(self):  # noqa:D102
        ch = self._children()
        if ch is None:
            return None
        if len(ch.objects) == 1:
            return ch
        return ch.combine(tol=0.001)

    def intersection(self):  # noqa:D102
        ch = self._children()
        if ch is None:
            return None
        if len(ch) == 1:
            return ch

        ws = cq.Workplane("XY")
        ws.add(ch.objects[0])

        for obj in ch.objects[1:]:
            ws = ws.intersect(obj, clean=False, tol=0.001)
        return ws.clean()

    def _children(self, idx=None, _ch=None):  # noqa:D102
        if _ch is None:
            _ch = self.vars["_e_children"]
        cws = self.eval(node=_ch)
        if cws is None:
            return None
        if idx is None:
            return cws

        ws = cq.Workplane("XY")
        if isinstance(idx, int):
            ws.add(cws.objects[idx])
        else:
            # assume it's a slice
            for obj in cws.objects[idx]:
                ws.add(obj)
        return ws

    def children(self, idx=None):  # noqa:D102
        try:
            ch = self.vars_dyn.prev.prev["_e_children"]
            # We need to peel back two layers and access the dynamic stack.
            # Our __init__ stores the variables to both
        except KeyError:
            return None
        return self._children(idx,ch)

    def import_(self, name):
        fn = self["_path"].parent / name
        from stl.mesh import Mesh

        vectors = Mesh.from_file(fn).vectors
        points = tuple(map(tuple, vectors.reshape((vectors.shape[0] * vectors.shape[1], 3))))
        faces = [(i, i + 1, i + 2) for i in range(0, len(points), 3)]
        return self.polyhedron(points, faces)

    def polyhedron(self, points, faces, convexity=None):
        from cqmore import Workplane
        return Workplane().polyhedron(points, faces)

    def polygon(self, points, paths=None):
        if paths is None:
            p_ext = points
            p_int = []
        else:
            p_ext = [points[x] for x in paths[0]]
            p_int = [ [points[x] for x in xx] for xx in paths[1:] ]
        ws = cq.Workplane("XY").polyline(p_ext).close()
        for x in p_int:
            ws = ws.polyline(x).close()
        return ws

    def debug(self):
        ch = self.vars["_e_children"]
        cws = self.eval(node=ch)
        return cws

    def linear_extrude(self, height, center=False, convexity=None, twist=0,
            slices=0, scale=1):
        if scale != 1 and twist != 0:
            warnings.warn("Scaling+twisting not yet supported")
            scale = 1
        if scale != 1:
            warnings.warn("Scaling doesn't work yet")
            scale = 1
        ch = self.vars["_e_children"]
        cws = self.eval(node=ch)
        if cws is None:
            return None
        if twist:
            res = cws.twistExtrude(height, -twist, combine=False)
        elif scale == 1:
            res = cws.extrude(height, combine=False)
        else:
            warnings.warn("Scaling doesn't work yet")
            res = cws.workplane(offset=height)
            res = res.loft(combine=False, clean=True)
            res = None
        if center:
            res = res.translate([0, 0, -height / 2])
        return res

    def scale(self, v):
        if isinstance(v,(float,int)):
            x,y,z = v,v,v
        else:
            x,y,z = v

        ch = self.vars["_e_children"]
        cws = self.eval(node=ch)
        if cws is None:
            return None
        warnings.warn("Scaling doesn't work yet")
        return cws

        ws = cq.Workplane("XY")
        m = cq.Matrix([[x,0,0,0],[0,y,0,0],[0,0,z,0]])
        for obj in cws.objects:
            ws = ws.add(obj.transformShape(m))
        return ws

    def rotate_extrude(self, angle=360, convexity=None):
        ch = self.vars["_e_children"]
        cws = self.eval(node=ch)
        if cws is None:
            return None

        ws = cq.Workplane("XY")
        for obj in cws.objects:
            ws = ws.add(obj)  # SIGH
        res = ws.toPending().revolve(abs(angle),(0,0,0),(0,1,0)).rotate((0, 0, 0), (1, 0, 0), 90)
        if angle < 0:
            res = res.rotate((0, 0, 0), (0, 0, 1), -angle)
        return res


    def color(self, c, a=None):
        warnings.warn("Color is not yet supported")
        ch = self.vars["_e_children"]
        return self.eval(node=ch)

    def square(self, size=1, center=False):
        if isinstance(size,(int,float)):
            x,y = size,size
        else:
            x,y = size

        return cq.Workplane("XY").rect(x,y, centered=center)

    def text(self, t, size=10, font=None, halign="left", valign="baseline",
            spacing=1, direction="ltr", language=None, script=None):

        args = {}
        if font is not None:
            args["font"] = font
        if halign is not None:
            args["halign"] = halign
        if valign is not None:
            args["valign"] = valign
        if spacing != 1:
            warnings.warn("Text spacing is not yet supported")
        if direction != "ltr":
            warnings.warn("Text direction is not yet supported")
        res = cq.Workplane("XY").text(t, size, 1, cut=False, **args)
        res = res.faces("<Z").wires().toPending()
        return res

    def str(self, *x):
        return "".join(str(y) for y in x)

    def chr(self, *x):
        res = ""
        for y in x:
            if isinstance(y,int):
                res += chr(y)
            else:
                res += "".join(chr(z) for z in y)
        return res

    def ord(self, x):
        try:
            return ord(x)
        except ValueError:
            return None

class MainEnv(Env):
    "main environment with global variables"

    def __init__(self, name="_main", vars_dyn=None):
        vars = Vars(name=name)
        super().__init__(parent=vars, name=name, vars_dyn=vars_dyn)
        self.vars["$fn"] = 999
        self.vars["$fa"] = 0
        self.vars["$fs"] = 0.001
        self.vars["$preview"] = 0
