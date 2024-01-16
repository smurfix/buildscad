from __future__ import annotations

import cadquery as cq
from .vars import Vars
from functools import partial

class Env:
    def __init__(self, name:str|None = None, parent:Env|None = None, init:dict|None=None):
        self.vars = Vars(name=name, parent=parent.vars if parent else None, init=init)
        self.parent = parent

    def __getitem__(self, k):
        try:
            fn = self.vars[k]
        except KeyError:
            return getattr(self,k)
        else:
            if callable(fn):
                fn = partial(fn, _env=self)
            return fn

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

        
