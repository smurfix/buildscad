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
import random

from arpeggio import ParseTreeNode as Node

from . import env as env_
from .env import DynEnv
from .blocks import Function

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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    VEC = TypeVar("VEC", tuple[float,float] | tuple[float,float,float])

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

        token = env_.set(self.env)
        try:
            val = vars[self.fn]
            if not callable(val):
                raise TypeError(f"Not callable: {val}")
            return val(*a, **k)
        finally:
            env_.reset(token)


class EnvEval:
    """Deferred evaluator."""

    def __init__(self, node):
        self.node = node

    def __call__(self, /, env):
        from .eval import Eval
        token = env_.set(env)
        try:
            return Eval(env).eval(self.node)
        finally:
            env_.reset(token)


class _Fns(DynEnv):
    def version(self):  # noqa:D102
        return "0.1.0"

    def echo(self, *a, **k):  # noqa:D102
        class DE:
            def __repr__(self):
                return ", ".join(f"{k} = {v !r}" for k, v in k.items())

        if k:
            a = a + (DE(),)
        print("ECHO:", ", ".join(repr(x) for x in a))


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

    def ord(self, x: str) -> int:
        try:
            return ord(x)
        except ValueError:
            return None

    def rands(self, min: float, max:float, n:int, seed=None) -> float:
        if seed is None:
            r = random.random
        else:
            r=random.Random(seed=seed).random

        rd = max-min
        return [ r()*rd+min for _ in range(n)]

    def cross(self, x:VEC, y: VEC):
        if len(x) == 2 and len(y) == 2:
            return x[0]*y[1] * x[1]*y[0]
        elif len(x) == 3 and len(y) == 3:
            return [
                    x[1]*y[2] - x[2]*y[1],
                    x[2]*y[0] - x[0]*y[2],
                    x[0]*y[1] - x[1]*y[0],
                    ]
        else:
            raise ValueError(f"Not two 2d or 3d vectors: {x !r} / {y !r}")

    def abs(self, x: float) -> float:
        return abs(x)

    def sign(self, x: float) -> int:
        return 0 if x == 0 else 1 if x>0 else -1

    def norm(self, *x: float) -> float:
        return math.sqrt(sum(v*v for v in x))

    def pow(self, x: float, y: float) -> float:
        return math.pow(x,y)

    def min(self, *x: float) -> float:
        return min(*x)

    def max(self, *x: float) -> float:
        return max(*x)

    def floor(self, x: float) -> float:
        return math.floor(x)

    def round(self, x: float) -> float:
        return round(x, 0)

    def len(self, x: list|tuple|str) -> int:
        return len(x)

    def ceil(self, x: float) -> float:
        return math.ceil(x)

    def log(self, x: float) -> float:
        return math.log(x)

    def exp(self, x: float) -> float:
        return math.exp(x)

    def sqrt(self, x: float) -> float:
        return math.sqrt(x)

    def sin(self, x: float) -> float:
        return math.sin(x * math.pi / 180)

    def cos(self, x: float) -> float:
        return math.cos(x * math.pi / 180)

    def tan(self, x: float) -> float:
        return math.tan(x * math.pi / 180)

    def asin(self, x: float) -> float:
        return math.asin(x) * 180 / math.pi

    def acos(self, x: float) -> float:
        return math.acos(x) * 180 / math.pi

    def atan(self, x: float) -> float:
        return math.atan(x) * 180 / math.pi

    def atan2(self, x: float, y: float) -> float:
        return math.atan2(x, y) * 180 / math.pi

    def is_undef(self, x:Any) -> bool:
        return x is None

    def is_bool(self, x:Any) -> bool:
        return isinstance(x, bool)

    def is_num(self, x:Any) -> bool:
        return isinstance(x (int,float))

    def is_string(self, x:Any) -> bool:
        return isinstance(x, str)

    def is_list(self, x:Any) -> bool:
        return isinstance(x, (list, tuple))

    def is_function(self, x:Any) -> bool:
        return callable(x) or isinstance(x, Function)

class _Mods(DynEnv):
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

    def for_(self, _intersect=False, **vars):

        if not len(vars):
            raise ValueError("'for' called without variables")

        ch = self.child
        res = None
        xenv = DynEnv(ch, self)
        venv = ch.parent

        def _for(**vs):
            nonlocal res

            if vs:
                var, stepper = vs.popitem()
                stp= stepper.step if isinstance(stepper.step, (int, float)) else self.eval(node=stepper.step)
                for val in (
                    stepper
                    if isinstance(stepper, (list, tuple))
                    else range(
                        self.eval(node=stepper.start),
                        self.eval(node=stepper.end)+stp,
                        stp,
                    )
                ):
                    venv.set_var(var, val)
                    _for(**vs)
            else:
                r = xenv.build_one(ch)
                if r is None:
                    return
                elif res is None:
                    res = r
                elif _intersect:
                    res &= r
                else:
                    res += r

        _for(**vars)
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

    def translate(self, v) -> Shape:  # noqa:D102
        ch = self.child_union()
        if ch is None:
            return None
        return ch.translate(v)

    def rotate(self, a=None, v=None) -> Shape:  # noqa:D102
        ch = self.child_union()
        if ch is None:
            return None
        if v is not None and v != [0, 0, 0]:
            if v == [1,0,0]:
                return ch.rotate(Axis.X,a)
            if v == [0,1,0]:
                return ch.rotate(Axis.Y,a)
            if v == [0,0,1]:
                return ch.rotate(Axis.Z,a)

            # now things get difficult
            from scipy.spatial.transform import Rotation
            vl = math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2])
            r = Rotation.from_rotvec(tuple(x/vl*a for x in v), degrees=True)
            a = r.as_euler("xyz", degrees=True)
        elif isinstance(a, (float, int)):
            return ch.rotate(Axis.Z, a)

        if a[0]:
            ch = ch.rotate(Axis.X, a[0])
        if a[1]:
            ch = ch.rotate(Axis.Y, a[1])
        if a[2]:
            ch = ch.rotate(Axis.Z, a[2])
        return ch

    def difference(self) -> Shape:  # noqa:D102
        ch = iter(self.children())
        res = next(ch)

        for c in ch:
            res -= c
        return res

    def union(self) -> Shape:  # noqa:D102
        return self.child_union()

    def intersection(self) -> Shape:  # noqa:D102
        res = None
        for obj in self.children():
            if obj is None:
                continue
            if res is None:
                res = obj
            else:
                res &= obj
        return res.clean()

    def resolve(self, idx=None) -> Shape:
        _ch = self.work
        if idx is not None:
            as_list = True

        ev = Eval(self)
        if idx is None:
            return ev.union()
        return ev.eval(self.work[idx])

    def resolve_list(self) -> list:
        from .eval import Eval
        ev = Eval(Env(self))
        ev.eval(_ch)
        if idx is None:
            return ev.union()
        res = [ ev.eval(c) for c in ev.env.work ]

        if idx is None:
            return res
        return res[idx]

    def children(self, idx=None) -> Shape:  # noqa:D102
        return self.one_child(idx)

    def import_(self, name) -> Shape:
        fn = self["_path"].parent / name
        from stl.mesh import Mesh

        vectors = Mesh.from_file(fn).vectors
        points = tuple(map(tuple, vectors.reshape((vectors.shape[0] * vectors.shape[1], 3))))
        faces = [(i, i + 1, i + 2) for i in range(0, len(points), 3)]
        return self.polyhedron(points, faces)

    def polyhedron(self, points, faces, convexity=None) -> Shape:

        points = [tuple(x) for x in points]

        def PL(path):
            return Polyline(*((points[x]) for x in path), close=True)

        return Solid.make_solid(Shell.make_shell(Face.make_from_wires(PL(face)) for face in faces))

    def polygon(self, points, paths=None) -> Sketch:
        if paths is None:
            p_ext = [tuple(x) for x in points]
            p_int = []
        else:
            p_ext = [tuple(points[x]) for x in paths[0]]
            p_int = [[tuple(points[x]) for x in xx] for xx in paths[1:]]

        def PL(pts):
            res = Polyline(pts, close=True)
            return make_face(res, Plane.XY)

        res = PL(p_ext)
        for x in p_int:
            res -= PL(x)
        return res

    def debug(self):
        breakpoint()

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

    def scale(self, v) -> Shape:
        if isinstance(v, (float, int)):
            x, y, z = v, v, v
        else:
            x, y, z = v

        ch = self.child_union()
        if res is None:
            return None
        return scale(res, (x, y, z))

    def rotate_extrude(self, angle=360, convexity=None) -> Shape:
        ch = self.child_union()
        if res is None:
            return None

        res = revolve(res, Axis.Y, revolution_arc=abs(angle))
        res = res.rotate(Axis.X, 90)
        if angle < 0:
            res = res.rotate(Axis.Z, angle)
        return res

    def color(self, c, a=None) -> Shape:
        warnings.warn("Color is not yet supported")
        return self.child_union()

    def square(self, size=1, center=False) -> Shape:
        if isinstance(size, (int, float)):
            x, y = size, size
        else:
            x, y = size

        return Rectangle(
            x, y, align=(Align.CENTER, Align.CENTER) if center else (Align.MIN, Align.MIN),
        )

    def circle(self, r=None, d=None) -> Shape:
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
    ) -> Shape:
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
