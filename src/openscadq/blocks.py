from __future__ import annotations

from contextvars import Token

from . import env

class Evalable:
    """
    Superclass for things that, when evaluated dynamically,
    return a CAD object (or ``None``).
    """
    def eval(self, env:DynEnv) -> Shape|None:
        raise NotImplementedError


class _Call(Evalable):
    def _collect(self, env, a, kw) -> DynEnv:
        "function/module call: apply arguments and build a d"

        p = dict(**self.params[1])

        p.update(kw)
        off = 0
        vl = list(self.params[0]) + list(self.params[1].keys())
        for v in a:
            try:
                p[vl[off]] = v
            except IndexError:
                warnings.warn(f"Too many params for {self.name}")
                break
            off += 1
        for v in vl:
            if v in p:
                continue
            elif v.startswith("$"):
                # $-variables get to be dynamically scoped
                try:
                    p[v] = env.var(v)
                except KeyError:
                    pass
                else:
                    continue
            warnings.warn(f"no value for {v !r}")
            p[v] = None

        for k, v in p.items():
            env[k] = v


class Function(_Call):
    def __init__(self, env:StaticEnv, name: str, params: Node, body: Node):
        self.name = name
        self.env = env
        self.params = params
        self.body = body

    """Encapsulates a function declaration"""
    def eval_args(self, env, a, kw):
        env = DynEnv(self.env, env)
        self._collect(env, a, kw)
        return env.eval(self.body)


class Module(_Call):
    def __init__(self, name: str, params: Node, body: Node):
        self.name = name
        self.params = params
        self.body = body

    """Encapsulates a module declaration"""
    def eval_args(self, env, a, kw):
        env = DynEnv(self.body, env)
        self._collect(env, a, kw)
        return env.build()


class Statement(Evalable):
    """Encapsulates a single statement, i.e. without braces"""
    def __init__(self, env:StaticEnv, body: Node):
        self.env = StaticEnv(env)
        self.body = body

    def build_with(self, env:DynEnv):
        e = DynEnv(env.static,env, with_vars=True)
        return e.eval(self.body)
        # return DynEnv(self.env,env).eval(self.body)


class ParentStatement(Statement):
    """Encapsulates a function/module call with a child node"""
    def __init__(self, env:StaticEnv, body: Node, child: Evalable):
        super().__init__(env, body)
        self.child = child

    def build_with(self, env:DynEnv):
        e = DynEnv(env.static,env, with_vars=True)
        e.child = self.child
        return e.eval(self.body)


class Variable:
    """Encapsulates a variable assignment"""
    def __init__(self, env:StaticEnv, name: str, body: Node):
        self.env = env
        self.name = name
        self.body = body

    def eval_with(self, env:DynEnv):
        return DynEnv(self.env,env).eval(self.body)

# annoying recursive imports

from .env import StaticEnv, DynEnv
