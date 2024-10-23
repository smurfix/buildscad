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

from . import env
from .vars import Vars

from build123d import (
    Align,
    Axis,
    Box,
    Circle,
    Compound,
    Face,
    Plane,
    Polyline,
    Pos,
    Rectangle,
    Rot,
    Shell,
    Solid,
    Sphere,
    Text,
    extrude,
    loft,
    make_face,
    revolve,
    scale,
)


class ForStep:
    def __init__(self, start, end, step=1):
        self.start = start
        self.end = end
        self.step = step


class EnvCall:
    """Environment-specific function call."""

    def __init__(self, fn, env):
        self.fn = fn
        self.env = env
        self.is_new = False

    def __call__(self, *a, **k):  # noqa:D102  # XXX
        vars = self.env.vars_dyn if self.fn[0] == "$" else self.env.vars

        token = env.set(self.env)
        try:
            val = vars[self.fn]
            if not callable(val):
                raise TypeError(f"Not callable: {val}")
            return val(*a, **k)
        finally:
            env.reset(token)


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
            self.vars_dyn = (
                vars_dyn if vars_dyn is not None else parent.vars_dyn.child(name, init=init)
            )
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
            try:
                try:
                    return getattr(self, k)
                except AttributeError:
                    if k[-1] == "_" or k[0] == "_":
                        raise
                    return getattr(self, k + "_")
            except AttributeError:
                raise KeyError(k) from None
        else:
            if isinstance(fn, EnvCall):
                pass
            elif callable(fn):
                fn = EnvCall(k, env=self)
            return fn

    def __setitem__(self, k, v):
        (self.vars_dyn if k[0] == "$" else self.vars)[k] = v

    def __delitem__(self, k):
        if k[0] != "$" or k[-1] != "$":
            raise ValueError("Don't even try to delete variables")
        del self.vars_dyn[k]

    def set(self, k, v):
        "__setitem__ without the dup warning"
        (self.vars_dyn if k[0] == "$" else self.vars).set(k, v)

    def __contains__(self, k):
        return k in (self.vars_dyn if k[0] == "$" else self.vars)

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

        return Sphere(r)

    def cube(self, size=1, center=False):  # noqa:D102
        if isinstance(size, (int, float)):
            x, y, z = size, size, size
        else:
            x, y, z = size
        res = Box(x, y, z)
        if not center:
            res = Pos(x / 2, y / 2, z / 2) * res
        return res

    def eval(self, node, env=None):
        if env is None:
            env = self
        ev = Eval(node, env=env)
        return ev.eval()

    def for_(self, _intersect=False, **var):

        if len(var) != 1:
            if len(var):
                raise ValueError("'for' called without variables")
            else:
                raise ValueError(
                    f"'for' called with more than one variable ({','.join(var.keys())})",
                )
        var, stepper = next(iter(var.items()))

        res = None
        e = Env(self)
        ch = self.vars["_e_children"]

        for val in (
            stepper
            if isinstance(stepper, (list, tuple))
            else range(
                self.eval(node=stepper.start),
                self.eval(node=stepper.end),
                stepper.step
                if isinstance(stepper.step, (int, float))
                else self.eval(node=stepper.step),
            )
        ):
            e.set(var, val)

            r = self.eval(node=ch, env=e)

            if r is None:
                continue

            elif res is None:
                res = r
            elif _intersect:
                res &= r
            else:
                res += r

        return res

    def intersection_for_(self, **var):
        return self.for_(_intersect=True, **var)

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
            r2 = r1

        res = Circle(r1)
        if r1 == r2:
            res = extrude(res, h)
        else:
            res = loft((res, Pos(0, 0, h) * Circle(r2)))
        if center:
            res = Pos(0, 0, -h / 2) * res
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
        if v is not None and v != [0, 0, 0]:
            return ch.rotate(v, a)
        elif isinstance(a, (float, int)):
            return ch.rotate(Axis.Z, a)
        else:
            if a[0]:
                ch = ch.rotate(Axis.X, a[0])
            if a[1]:
                ch = ch.rotate(Axis.Y, a[1])
            if a[2]:
                ch = ch.rotate(Axis.Z, a[2])
            return ch

    def difference(self):  # noqa:D102
        ch = self._children(as_list=True)

        print(ch)
        if not ch:
            return None
        if len(ch) == 1:
            return ch

        res = ch[0]
        if res is None:
            return None
        if isinstance(res, Compound) and res._dim is None:
            breakpoint()
        if isinstance(res, (tuple, list)):
            if len(res) == 1:
                res = res[0]
            else:
                raise ValueError("too many elements")

        ct = []
        for obj in ch[1:]:
            if obj is None:
                continue
            ct.append(obj)
        if not ct:
            return res
        if False:
            rr = res.cut(*ct).clean()
        else:
            rr = res
            for c in ct:
                rr -= c
        return rr

    def union(self):  # noqa:D102
        return self._children()

    def intersection(self):  # noqa:D102
        ch = self._children(as_list=True)
        if ch is None:
            return None
        res = None
        for obj in ch:
            if obj is None:
                continue
            if res is None:
                res = obj
            else:
                res &= obj
        return res.clean()

    def _children(self, idx=None, _ch=None, as_list=False):
        if _ch is None:
            _ch = self.vars["_e_children"]
        if idx is not None:
            as_list = True

        if as_list:
            self.vars_dyn["$list$"] = True
            try:
                res = self.eval(node=_ch)
            finally:
                if "$list$" in self.vars_dyn:
                    del self.vars_dyn["$list$"]
        else:
            res = self.eval(node=_ch)

        if res is None:
            return None
        if idx is None:
            return res
        return res[idx]

    def children(self, idx=None):  # noqa:D102
        try:
            ch = self.vars_dyn.prev.prev["_e_children"]
            # We need to peel back two layers and access the dynamic stack.
            # Our __init__ stores the variables to both
        except KeyError:
            return None
        return self._children(idx, ch)

    def import_(self, name):
        fn = self["_path"].parent / name
        from stl.mesh import Mesh

        vectors = Mesh.from_file(fn).vectors
        points = tuple(map(tuple, vectors.reshape((vectors.shape[0] * vectors.shape[1], 3))))
        faces = [(i, i + 1, i + 2) for i in range(0, len(points), 3)]
        return self.polyhedron(points, faces)

    def polyhedron(self, points, faces, convexity=None):

        points = [tuple(x) for x in points]

        def PL(path):
            return Polyline(*((points[x]) for x in path), close=True)

        return Solid.make_solid(Shell.make_shell(Face.make_from_wires(PL(face)) for face in faces))

    def polygon(self, points, paths=None):
        if paths is None:
            p_ext = [tuple(x) for x in points]
            p_int = []
        else:
            p_ext = [tuple(points[x]) for x in paths[0]]
            p_int = [[tuple(points[x]) for x in xx] for xx in paths[1:]]
        print(p_ext, p_int)

        def PL(pts):
            res = Polyline(pts, close=True)
            return make_face(res, Plane.XY)

        res = PL(p_ext)
        for x in p_int:
            res -= PL(x)
        return res

    def debug(self):
        ch = self.vars["_e_children"]
        res = self.eval(node=ch)
        return res

    def linear_extrude(self, height, center=False, convexity=None, twist=0, slices=0, scale=1):
        if scale != 1 and twist != 0:
            warnings.warn("Scaling+twisting not yet supported")
            scale = 1
        if scale != 1:
            warnings.warn("Scaling doesn't work yet")
            scale = 1
        ch = self.vars["_e_children"]
        res = self.eval(node=ch)
        if res is None:
            return None
        if scale == 1 and twist == 0:
            res = extrude(res, amount=height)
        else:
            res = loft((res, Pos(0, 0, height) * Rot(0, 0, -twist) * res.scale(scale)))
        #       else:
        #           warnings.warn("Scaling / twisting linear extrusions doesn't work yet")
        #           res = None
        if center:
            res = Pos(0, 0, -height / 2) * res
        return res

    def scale(self, v):
        if isinstance(v, (float, int)):
            x, y, z = v, v, v
        else:
            x, y, z = v

        ch = self.vars["_e_children"]
        res = self.eval(node=ch)
        if res is None:
            return None
        return scale(res, (x, y, z))

    def rotate_extrude(self, angle=360, convexity=None):
        ch = self.vars["_e_children"]
        res = self.eval(node=ch)
        if res is None:
            return None

        res = revolve(res, Axis.Y, revolution_arc=abs(angle))
        res = res.rotate(Axis.X, 90)
        if angle < 0:
            res = res.rotate(Axis.Z, angle)
        return res

    def color(self, c, a=None):
        warnings.warn("Color is not yet supported")
        ch = self.vars["_e_children"]
        return self.eval(node=ch)

    def square(self, size=1, center=False):
        if isinstance(size, (int, float)):
            x, y = size, size
        else:
            x, y = size

        return Rectangle(
            x, y, align=(Align.CENTER, Align.CENTER) if center else (Align.MIN, Align.MIN),
        )

    def circle(self, r=None, d=None):
        if r is None:
            if d is None:
                r = 1
            else:
                r = d / 2
        elif d is not None:
            warnings.warn("circle: parameters are ambiguous")

        return Circle(r)

    def text(
        self,
        t,
        size=10,
        font=None,
        halign="left",
        valign="baseline",
        spacing=1,
        direction="ltr",
        language=None,
        script=None,
    ):
        def _align(x):
            if x is None or x == "baseline":
                return None  # Align.NONE
            if x in ("left", "top"):
                return Align.MIN
            if x in ("right", "bottom"):
                return Align.MAX
            if x == "center":
                return Align.CENTER

            warnings.warn(f"What alignment is {x!r}?")
            return Align.NONE

        args = {"align": (_align(halign), _align(valign))}
        if font is not None:
            args["font"] = font
        if direction != "ltr":
            warnings.warn("Explicit text direction is not supported")
        size *= 1.4  # XXX measured delta between openscad and build123d
        res = Text(t, font_size=size, **args)
        if spacing != 1:
            warnings.warn("Text spacing is not yet supported")
            # TODO maybe stretch it instead?
        return res

    def str(self, *x):
        return "".join(str(y) for y in x)

    def chr(self, *x):
        res = ""
        for y in x:
            if isinstance(y, int):
                res += chr(y)
            else:
                res += "".join(chr(z) for z in y)
        return res

    def ord(self, x):
        try:
            return ord(x)
        except ValueError:
            return None

    def min(self, *x):
        return min(*x)

    def max(self, *x):
        return max(*x)

    def floor(self, x):
        return math.floor(x)

    def ceil(self, x):
        return math.ceil(x)

    def sin(self, x):
        return math.sin(x * math.pi / 180)

    def cos(self, x):
        return math.cos(x * math.pi / 180)

    def tan(self, x):
        return math.tan(x * math.pi / 180)

    def atan(self, x):
        return math.atan(x) * 180 / math.pi

    def atan2(self, x, y):
        return math.atan2(x, y) * 180 / math.pi


class MainEnv(Env):
    "main environment with global variables"

    def __init__(self, name="_main", vars_dyn=None):
        ivars = Vars(name=f"{name} (init)")
        vars = Vars(name=name, parent=ivars)
        super().__init__(parent=vars, name=name, vars_dyn=vars_dyn)
        ivars["$fn"] = 999
        ivars["$fa"] = 0
        ivars["$fs"] = 0.001
        self.vars["$preview"] = 0
