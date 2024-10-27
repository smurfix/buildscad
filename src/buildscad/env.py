from __future__ import annotations

import sys
from contextvars import Token

from . import cur_env, main_env
from build123d import Shape

class _working:
    pass

class _unknown:
    pass


### Building blocks


### Environment handling

class NullEnv:
    "An environment that does nothing"
    _level = 0

    def var(self, name):
        breakpoint()
        raise KeyError(name)
    def mod(self, name):
        raise KeyError(name)
    def func(self, name):
        raise KeyError(name)

    def trace(self, *a, **k):
        if self["$trace"]:
            main_env.get().trace_(a, k)

_null = NullEnv()


class _Env(NullEnv):
    def __init__(self, parent:StaticEnv|DynEnv|NullEnv = _null):
        self.parent = parent

        # Variables, functions and modules have each their own name space
        self.vars: dict[Variable,Node] = dict()
        self.funcs: dict[Function,Node] = dict()
        self.mods: dict[Module,Node] = dict()

    def var(self, name: str):
        """returns the node that computes a variable"""
        res = self.vars.get(name, _null)
        if res is not _null:
            return res
        return self.parent.var(name)
        
    def func(self, name: str):
        """returns the node that computes a variable"""
        res = self.funcs.get(name, None)
        if res is None:
            res = self.vars.get(name, None)
        if res is not None:
            return res
        return self.parent.func(name)
        
    def mod(self, name: str):
        """returns the node that computes a module"""
        res = self.mods.get(name, None)
        if res is not None:
            return res
        return self.parent.mod(name)

    def add_var(self, name: str, body: Node):
        if name in self.vars:
            warnings.warn(f"Dup assignment of variable {name !r}")
        else:
            self.vars[name] = Variable(self, name, body)

    def add_func_(self, name:str, fn: Callable|Evalable) -> None:
        if name in self.funcs:
            warnings.warn(f"Dup assignment of function {name !r}")
        else:
            self.funcs[name] = fn

    def add_func(self, name:str, params: Node, body:Node):
        self.add_func_(name, Function(self, name, params, body))

    def add_mod_(self, name:str, mod: Callable|Evalable) -> None:
        if name in self.mods:
            warnings.warn(f"Dup assignment of module {name !r}")
        else:
            self.mods[name] = mod

    def add_mod(self, name:str, params: Node, body:Node):
        self.add_mod_(name, Module(self, name, params, body))


class _Eval:
    _level = 0
    debug:bool = False

    def eval(self, node:Node) -> Evalable|None:
        """Create something """
        while True:
            try:
                p = getattr(self, f"_e_{node.rule_name}")
                if self.debug:
                    print(" " * self._level, ">", node.rule_name)

            except AttributeError:
                if not node.rule_name:
                    raise RuntimeError("trying to interpret a terminal element", node) from None
                print(node.tree_str(), file=sys.stderr)
                raise RuntimeError(f"Syntax not implemented: {node.rule_name}")

            else:
                try:
                    if len(node) == 1 and hasattr(p, "skip1"):
                        node = node[0]
                        continue
                except TypeError:
                    pass
            break

        self._level += 1
        try:
            res = p(node)
        except ArityError:
            print(f"ParamCount: {node.rule_name}", file=sys.stderr)
            print(node.tree_str(), file=sys.stderr)
            raise
        finally:
            self._level -= 1

        if self.debug:
            print(" " * self._level, "<", res)

        return res


class StaticEnv(_Eval, _Env):
    """.
    Static environment, collects code blocks.
    """

    def __new__(cls, *a, **kw):
        # Workaround for recursive imports
        class StaticEnv_(cls, _StaticRules, Evalable):
            pass
        return object.__new__(StaticEnv_)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # self.child: StaticEnv|None = None
        self.work: list[ModCall] = []

    def add_work(self, obj:StaticEnv|Statement):
        self.work.append(obj)

    def build_with(self, env: DynEnv):
        env = DynEnv(self, env)
        return env.build()


    @property
    def child(self):
        raise NotImplementedError


class SpecialEnv(StaticEnv):
    """.
    Static environment, collects code blocks.
    """
    def __new__(cls, *a, **kw):
        # Workaround for recursive imports
        class SpecialEnv_(cls, _StaticRules, Evalable):
            pass
        return object.__new__(SpecialEnv_)

    def set_var(self, name: str, value: Any) -> None:
        """Override a variable"""
        self.vars[name] = value
    
    def set_func(self, name: str, value: Callable) -> None:
        """Override a function"""
        self.funcs[name] = value
    
    def set_mod(self, name: str, value: Callable) -> None:
        """Override a module"""
        self.mods[name] = value
    

class DynEnv(_Eval, NullEnv):
    """
    Dynamic environment, for evaluation.
    """

    # contextvar token
    _token:Token = None
    _recurse:int = 0

    child:Evalable|None = None
    _child_env_:DynEnv|None = None
    _child_res:Shape|list[Shape|None|_unknown]|Literal[_unknown] = _unknown

    def __new__(cls, *a, **kw):
        class DynEnv_(cls, _DynRules, Evalable):
            pass
        return object.__new__(DynEnv_)

    def __init__(self, static:StaticEnv, dyn: DynEnv|NullEnv = _null, with_vars=False):
        """
        """
        if not isinstance(dyn,DynEnv) and dyn is not _null:
            breakpoint()
        if not isinstance(static,StaticEnv):
            breakpoint()
        assert isinstance(static,StaticEnv)
        assert isinstance(dyn,DynEnv) or dyn is _null, dyn
        self.static = static
        self.dyn = dyn

        self._level = dyn._level

        # actual values for variables
        self.vars: dict[str,Any] = dyn.vars if with_vars else {}

    def reset_child(self):
        self._child_env_ = None
        self._child_res = _unknown

    def __getitem__(self, k):
        return self.var(k)

    def __setitem__(self, k:str, v):
        self.vars[k] = v

    @property
    def _child_env(self):
        if self._child_env_ is not None:
            return self._child_env_
        child = self.child
        self._child_env_ = env = DynEnv(child, self)
        self._child_res = [_unknown] * len(child.work)
        return env

    def one_child(self, i:int) -> Shape|None:
        """Evaluate a single child node."""
        child = self.child
        if child is None:
            return None

        if isinstance(child,Statement):
            # explicit statement, single child
            if i != 0:
                return None
            if self._child_res is _unknown:
                self._child_res = child.eval(self)
            return self._child_res

        env = self._child_env
        if len(self._child_res) <= i:
            return None
        if (r := self._child_res[i]) is _unknown:
            node = child.work[i]
            r = env.eval(node)
            self._child_res[i] = r
        return r

    def child_union(self) -> Shape|None:
        res = None
        for r in self.children():
            if r is None:
                continue
            if res is None:
                res = r
            else:
                r2 = res + r
                self.trace(r2, "_add",res,r)
                res = r2
        return res

    def children(self) -> Iterator[Shape|None]:
        """Retrieve all children, starting with the first"""
        child = self.child
        if child is None:
            yield None
            return

        if isinstance(child,Statement):
            # explicit statement = single child
            if self._child_res is _unknown:
                self._child_res = child.eval(self)
            yield self._child_res
            return

        # {…} = possibly multiple children, new sub-env
        assert(isinstance(child, StaticEnv))
        env = self._child_env
        for i,node in enumerate(child.work):
            if (r := self._child_res[i]) is _unknown:
                r = node.build_with(self)
                self._child_res[i] = r
            yield r

    def var(self, name:str):
        """Eval a variable"""
        if name == "$children":
            if self.child is None:
                return 0
            return len(self.child.work)

        if name in self.vars:
            val = self.vars[name]
            if val is _working:
                raise RuntimeError(f"Recursive variable {name !r}")
            return val

        if name[0] == '$':
            try:
                vdef = self.dyn.var(name)
            except KeyError:
                vdef = self.static.var(name)
        else:
            vdef = self.static.var(name)
        self.vars[name] = _working
        try:
            if hasattr(vdef, "eval_with"):
                val = vdef.eval_with(self)
            elif hasattr(vdef, "_env_"):
                val = vdef(self)
            elif callable(vdef):
                with self:
                    val = vdef()
            else:
                val = vdef
        except Exception:
            del self.vars[name]
            raise
        self.vars[name] = val
        return val

    def set_var(self, name:str, n:Node):
        if name[0] != '$':
            raise RuntimeError("Name must start with a '$'")
        self.vars[name] = self.eval(n)

    def func(self, name, *a, **kw):
        """Eval a function"""
        try:
            fn = self.static.func(name)
        except KeyError:
            try: 
                fn = self.var(name)
            except KeyError:
                raise KeyError(name) from None

        if isinstance(fn, Variable):
            fn = fn.eval_with(self)

        if hasattr(fn,"eval_args"):
            return fn.eval_args(self, a, kw)
        if hasattr(fn, "_env_"):
            return fn(self, a, kw)
        # "foreign" function
        with self:
            return fn(*a, **kw)

    def mod(self, name, *a, **kw):
        """Eval a module"""
        fn = self.static.mod(name)
        if hasattr(fn,"eval_args"):
            return fn.eval_args(self, a, kw)
        if hasattr(fn, "_env_"):
            return fn(self, *a, **kw)
        # "foreign" function
        with self:
            return fn(*a, **kw)

    def build_one(self, b):
        if isinstance(b, Shape):
            return b
        elif hasattr(b,"build_with"):
            return b.build_with(self)
        elif hasattr(b,"_env_"):
            return b(env)
        elif callable(b):
            with self:
                return b()
        else:
            raise ValueError(f"Work list contains {b !r}", b)

    def build(self):
        """Helper to combine to-be-evaluated things"""
        res = None
        for b in self.static.work:
            r = self.build_one(b)

            if r is None:
                continue
            if res is None:
                res = r
            else:
                r2 = res + r
                self.trace(r2, "_add",res,r)
                res = r2
        return res

    def __enter__(self):
        if self._token is not None:
            if cur_env.get() is not self:
                raise RuntimeError("recursive call")
            self._recurse += 1
            return self
        self._token = cur_env.set(self)
        return self

    def __exit__(self, *tb):
        if self._recurse:
            self._recurse -= 1
        else:
            cur_env.reset(self._token)
            self._token = None

# annoying recursive imports

from .blocks import Function,Module,Variable,Evalable,Statement
from .rules import _DynRules, _StaticRules, ArityError
