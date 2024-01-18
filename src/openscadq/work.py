from __future__ import annotations

import cadquery as cq
from .vars import Vars
from functools import partial
import math
from contextlib import contextmanager

class EnvCall:
    def __init__(self, fn, env):
        self.fn = fn
        self.env = env
        self.is_new = False

    def __call__(self, *a, **k):
        return self.env.vars[self.fn](*a, _env=self.env, **k)

class Env:
    current_call = None

    def __init__(self, parent:Env|Vars, name:str|None = None, init:dict|None=None):
        if isinstance(parent,Env):
            self.parent = parent
            self.vars = parent.vars.child(name, init=init)
        else:
            if init is not None:
                raise ValueError("invalid")
            self.vars = parent
            self.parent = parent

    def __getitem__(self, k):
        if k == "$children":
            return len(self.vars["_e_children"])
        try:
            fn = self.vars[k]
        except KeyError:
            return getattr(self,k)
        else:
            if callable(fn):
                fn = EnvCall(k, env=self)
            return fn

    def set_cc(self, k, v):
        if self.current_call is None:
            self.vars[k] = v
        else:
            cc = self.current_call
            if not cc.is_new:
                cc.is_new = True
                cc.env = Env(name=cc.fn, parent=cc.env)
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

    def echo(self, *a, **k):
        class DE:
            def __repr__(self):
                return ", ".join(f"{k} = {v !r}" for k,v in k.items())
        if k:
            a = a+(DE(),)
        print("ECHO:", ", ".join(repr(x) for x in a))

    def sphere(self, r=None, d=None):
        if r is None:
            r = d/2
        return cq.Workplane("XY").sphere(r)

    def cube(self, size, center=False):
        if isinstance(size,(int,float)):
            x,y,z = size,size,size
        else:
            x,y,z = size
        res = cq.Workplane("XY").box(x,y,z)
        if not center:
            res = res.translate((x/2,y/2,z/2))
        return res

    def cylinder(self, h, r=None, r1=None, r2=None, d=None, d1=None,
            d2=None, center=False):
        if r is not None:
            r1 = r2 = r
        elif d is not None:
            r1 = r2 = r
        if d1 is not None:
            r1 = d1/2
        if d2 is not None:
            r2 = d1/2

        res = cq.Workplane("XY").circle(r1)
        if r1 == r2:
            res = res.extrude(h)
        else:
            res = res.workplane(offset=h).circle(r2).loft(combine=True)
        if center:
            res = res.translate([0,0,h/2])
        return res

    def translate(self, vec):
        return self.children().translate(vec)

    def children(self, idx=None):
        ch = self.vars["_e_children"]
        if idx is None:
            return ch
        if isinstance(idx,int):
            return ch[i]

        raise NotImplementedError("Child vectors")

        
class MainEnv(Env):
    def __init__(self, write_once:bool=True):
        vars = Vars(name="_main", write_once=write_once)
        super().__init__(parent=vars, name="_main")
        self.vars['$fn'] = 999
        self.vars['$fa'] = 0
        self.vars['$fs'] = 0.001
        self.vars['$preview'] = 0
