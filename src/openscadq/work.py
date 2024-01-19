from __future__ import annotations

import cadquery as cq
from .vars import Vars
import math
from contextlib import contextmanager
import warnings

class EnvCall:
    def __init__(self, fn, env):
        self.fn = fn
        self.env = env
        self.is_new = False

    def __call__(self, *a, **k):
        vars = self.env.vars_dyn if self.fn[0] == "$" else self.env.vars
        return vars[self.fn](*a, _env=self.env, **k)

class Env:
    current_call = None
    eval = None

    def __init__(self, parent:Env|Vars, name:str|None = None, init:dict|None=None, vars_dyn:Vars=None):
        if isinstance(parent,Env):
            self.parent = parent
            self.vars = parent.vars.child(name, init=init)
            self.vars_dyn = vars_dyn if vars_dyn is not None else parent.vars_dyn.child(name)
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
            return getattr(self,k)
        else:
            if isinstance(fn, EnvCall):
                pass
            elif callable(fn):
                fn = EnvCall(k, env=self)
            return fn

    def __setitem__(self, k, v):
        (self.vars_dyn if k[0] == "$" else self.vars)[k] = v

    def inject_vars(self, env):
        self.vars.inject(env.vars)
        self.vars_dyn.inject(env.vars_dyn)

    def set_cc(self, k, v):
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
        if isinstance(fn,EnvCall):
            self.current_call,cc = fn,self.current_call
            try:
                yield self
            finally:
                self.current_call = cc
        else:
            yield self

    PI = math.pi
    undef = None
    def version(self):
        return "0.1.0"

    def echo(self, *a, **k):
        class DE:
            def __repr__(self):
                return ", ".join(f"{k} = {v !r}" for k,v in k.items())
        if k:
            a = a+(DE(),)
        print("ECHO:", ", ".join(repr(x) for x in a))

    def sphere(self, r=None, d=None):
        if r is None:
            if d is None:
                r = 1
            else:
                r = d/2
        elif d is not None:
            warnings.warn("sphere: parameters are ambiguous")

        return cq.Workplane("XY").sphere(r)

    def cube(self, size=1, center=False):
        if isinstance(size,(int,float)):
            x,y,z = size,size,size
        else:
            x,y,z = size
        res = cq.Workplane("XY").box(x,y,z)
        if not center:
            res = res.translate((x/2,y/2,z/2))
        return res

    def cylinder(self, h=1, r1=None, r2=None, r=None, d=None, d1=None,
            d2=None, center=False):
        if (
                (r1 is not None) +
                (r2 is not None) +
                (d1 is not None) +
                (d2 is not None) +
                2*(r is not None) + 2*(d is not None)
            ) > 2 or (r1 is not None and d1 is not None) or (r2 is not None and d2 is not None):
            warnings.warn("cylinder: parameters are ambiguous")

        if r is not None:
            r1 = r2 = r
        if d is not None:
            r1 = r2 = d/2
        if d1 is not None:
            r1 = d1/2
        if d2 is not None:
            r2 = d1/2

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
            res = res.translate([0,0,-h/2])
        return res

    def translate(self, v):
        ch = self.children()
        if ch is None:
            return None
        return ch.translate(v)

    def rotate(self, a=None, v=None):
        ch = self.children()
        if ch is None:
            return None
        if v is not None:
            return ch.rotate((0,0,0),v,a)
        elif isinstance(a,(float,int)):
            return ch.rotate((0,0,0),(0,0,1),a)
        else:
            if a[0]:
                ch = ch.rotate((0,0,0),(1,0,0),a[0])
            if a[1]:
                ch = ch.rotate((0,0,0),(0,1,0),a[1])
            if a[2]:
                ch = ch.rotate((0,0,0),(0,0,1),a[2])
            return ch

    def difference(self):
        ch = self.children()
        if ch is None:
            return None
        if len(ch.objects) == 1:
            return ch

        ws = cq.Workplane("XY")
        ws.add(ch.objects[0])

        for obj in ch.objects[1:]:
            ws = ws.cut(obj, clean=False, tol=0.001)
        return ws.clean()

    def union(self):
        ch = self.children()
        if ch is None:
            return None
        if len(ch.objects) == 1:
            return ch
        return ch.combine(tol=0.001)

    def intersection(self):
        ch = self.children()
        if ch is None:
            return None
        if len(ch) == 1:
            return ch

        ws = cq.Workplane("XY")
        ws.add(ch.objects[0])

        for obj in ch.objects[1:]:
            ws = ws.intersect(obj, clean=False, tol=0.001)
        return ws.clean()

    def children(self, idx=None):
        ch = self.vars["_e_children"]
        cws = self.eval(node=ch)
        if cws is None:
            return None
        if idx is None:
            return cws

        ws = cq.Workplane("XY")
        if isinstance(idx,int):
            ws.add(cws.objects[idx])
        else:
            # assume it's a slice
            for obj in cws.objects[idx]:
                ws.add(obj)
        return ws

        
class MainEnv(Env):
    def __init__(self, name="_main", vars_dyn=None):
        vars = Vars(name=name)
        super().__init__(parent=vars, name=name, vars_dyn=vars_dyn)
        self.vars['$fn'] = 999
        self.vars['$fa'] = 0
        self.vars['$fs'] = 0.001
        self.vars['$preview'] = 0
