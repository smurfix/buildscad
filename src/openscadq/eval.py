"""
Evaluate a parsed OpenSCAD file.
"""
from __future__ import annotations

import math
import sys
import warnings
from functools import partial
from pathlib import Path

from .peg import Parser
from .work import Env, MainEnv

import cadquery as cq
from simpleeval import simple_eval

# ruff: noqa:ARG002


class ArityError(ValueError):
    "Wrong number of arguments"


def arity(n, a, b=None):
    "Checker for parse tree processors"
    if b is None:
        if len(n) != a:
            raise ArityError(n, a)
    elif not a <= len(n) <= b:
        raise ArityError(n, a, b)


class Function:
    """Wrapper for function calls"""

    def __init__(self, eval, name, params, body, env):
        self.eval = eval
        self.name = name
        self.params = params
        self.body = body
        self.env = env

    def __call__(self, *a, _env, **kw):
        "function call; apply arguments and interpret the body"
        p = dict(**self.params[1])

        p.update(kw)
        off = 0
        vl = list(self.params[0]) + list(self.params[1].keys())
        for v in a:
            p[vl[off]] = v
            off += 1
        for v in vl:
            if v in p:
                continue
            elif v.startswith("$"):
                # $-variables get to be dynamically scoped
                try:
                    p[v] = _env[v]
                except KeyError:
                    pass
                else:
                    continue
            warnings.warn(f"no value for {v !r}")
            p[v] = None

        e = Env(name=self.name, parent=self.env, vars_dyn=_env.vars_dyn)
        for k, v in p.items():
            e[k] = v

        return self.eval.eval(node=self.body, env=e)


class Module(Function):
    """Wrapper for method calls"""

    # incidentally same as for functions


class Eval:
    """Evaluator that steps through the parse tree and constructs the model from it"""

    defs: bool = None

    def __init__(self, nodes, env: Env | None = None, debug: bool = False):
        self.nodes = nodes
        if env is None:
            env = MainEnv()
        self.env = env
        self.debug = debug
        self.level = 0

    def set(self, k, v):
        """(forcibly) set a value"""
        self.env.vars.set(k, v)

    def _eval(self, n, e):
        try:
            p = getattr(self, f"_e_{n.rule_name}")
            self.level += 1
            if self.debug:
                print(" " * self.level, ">", n.rule_name)

        except AttributeError:
            if not n.rule_name:
                raise RuntimeError("trying to interpret a terminal element", n) from None
            print(f"Unknown: {n.rule_name}")
            print(n.tree_str())
            sys.exit(1)
        try:
            res = p(n, e)
        except ArityError:
            print(f"ParamCount: {n.rule_name}")
            print(n.tree_str())
            sys.exit(1)
        finally:
            self.level -= 1
        if self.debug:
            print(" " * self.level, "<", res)
        return res

    def _e_Input(self, n, e):
        return self._e__list(n, e)

    def _e__list(self, n, e):
        if self.defs:
            self._e__list_(n, e)
            return

        try:
            self.defs = True
            self._e__list_(n, e)
        finally:
            self.defs = False
        return self._e__list_(n, e)

    def _e__list_(self, n, e):
        ws = None
        for nn in n:
            r = self._eval(nn, e)
            if r is None:
                pass
            elif isinstance(r, cq.Workplane):
                if ws is None:
                    ws = cq.Workplane("XY")
                ws = ws.add(r)
            else:
                warnings.warn(f"Unknown result: {r !r}")
        return ws

    def _e_Include(self, n, e):
        """'include' statement.

        Adds the file as if it was textually included, except that
        variables from the included file can be overridden.
        """
        arity(n, 2)
        p = Parser(debug=False, reduce_tree=False)
        fn = n[1].value[1:-1]
        try:
            fn = e["_path"].parent / fn
        except AttributeError:
            fn = Path(fn)
        tree = p.parse(fn.read_text())
        ep = Env(parent=e, name=str(fn))
        res = self._eval(tree, ep)
        e.inject_vars(ep)
        return res

    def _e_Use(self, n, e):
        """'use' statement.

        Add the variables and functions defined by the used module (but
        *not* those it itself imports via 'use'!) to the current scope.
        """
        if not self.defs:
            return

        arity(n, 2)
        p = Parser(debug=False, reduce_tree=False)
        fn = n[1].value[1:-1]
        try:
            fn = e["_path"].parent / fn
        except AttributeError:
            fn = Path(fn)

        tree = p.parse(fn.read_text())

        ep = MainEnv(name=str(fn))
        self._eval(tree, ep)
        e.inject_vars(ep)

    def _e__descend(self, n, e):
        arity(n, 1)
        return self._eval(n[0], e)

    def _e_stmt_list(self, n, e):
        if self.defs:
            raise RuntimeError("This shouldn't happen")
        e = Env(parent=e)

        return self._e__list(n[1:-1], e)

    _e_explicit_child = _e_stmt_list

    def _e_pr_vec_empty(self, n, e):
        return ()

    def _e_pr_vec_elems(self, n, e):
        return self._eval(n[1], e)

    def _e_vector_elements(self, n, e):
        res = []
        off = 0
        while off < len(n):
            res.append(self._eval(n[off], e))
            off += 2
        return res

    def _e_expr_case(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        arity(n, 5)
        if res:
            return self._eval(n[2], e)
        else:
            return self._eval(n[4], e)

    def _e_logic_or(self, n, e):
        res = self._eval(n[0], e)
        off = 1
        while len(n) > off:
            if res:
                return res
            if n[off].value == "||":
                res = self._eval(n[off + 1], e)
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    def _e_logic_and(self, n, e):
        res = self._eval(n[0], e)
        off = 1
        while len(n) > off:
            if not res:
                return res
            if n[off].value == "&&":
                res = self._eval(n[off + 1], e)
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    def _e_equality(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off + 1], e)
            if n[off].value == "==":
                if res != res2:
                    return False
            elif n[off].value == "!=":
                if res == res2:
                    return False
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
            res = res2
        return True

    def _e_comparison(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off + 1], e)
            if n[off].value == "<":
                if res >= res2:
                    return False
            elif n[off].value == "<=":
                if res > res2:
                    return False
            elif n[off].value == ">=":
                if res < res2:
                    return False
            elif n[off].value == ">":
                if res <= res2:
                    return False
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
            res = res2
        return True

    def _e_addition(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off + 1], e)
            if n[off].value == "+":
                res += res2
            elif n[off].value == "-":
                res -= res2
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    def _e_multiplication(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off + 1], e)
            if n[off].value == "*":
                res *= res2
            elif n[off].value == "/":
                res /= res2
            elif n[off].value == "%":
                res %= res2
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    def _e_unary(self, n, e):
        arity(n, 1, 2)
        res = self._eval(n[-1], e)
        if len(n) == 2:
            if n[0].value == "+":
                pass
            elif n[0].value == "-":
                res = -res
            elif n[0].value == "!":
                res = not res
            else:
                raise ValueError("Unknown op", n[0])
        return res

    def _e_exponent(self, n, e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        arity(n, 3)
        exp = self._eval(n[2], e)
        if n[1].value == "^":
            return math.pow(res, exp)
        else:
            raise ValueError("Unknown op", n[1])

    def _e_call(self, n, e):
        res = self._eval(n[0], e)
        off = 1
        if off < len(n):
            with e.cc(res):
                app = self._eval(n[off], e)
                res = app(e.current_call or res)
            off += 1
        while off < len(n):
            app = self._eval(n[off], e)
            res = app(res)
            off += 1
        return res

    def _e_pr_Num(self, n, e):
        val = n.value
        try:
            return int(val)
        except ValueError:
            return float(val)

    def _e_pr_Sym(self, n, e):
        return e[n.value]

    def _e_pr_Str(self, n, e):
        return simple_eval(n.value)

    def _e_assignment(self, n, e):
        e[n[0].value] = self._eval(n[2], e)

    def _e_stmt_decl_fn(self, n, e):
        arity(n, 7, 8)
        name = n[1].value
        if len(n) == 8:
            params = self._eval(n[3], e)
        else:
            params = ((), {})
        body = n[-2]
        e[name] = Function(self, name, params, body, e)

    def _e_stmt_decl_mod(self, n, e):
        arity(n, 5, 6)
        name = n[1].value
        if name in e:
            return  # already defined

        if len(n) == 6:
            params = self._eval(n[3], e)
        else:
            params = ((), {})
        body = n[-1]
        e[name] = Module(self, name, params, body, e)

    def _e_fn_call(self, n, e):
        if self.debug:
            print(" " * self.level, "=", n)

        arity(n, 3, 4)
        e.eval = partial(self.eval, env=e)
        try:
            fn = e[n[0].value]
        except AttributeError:
            raise ValueError(f"Function {n[0].value !r} undefined") from None
        if len(n) == 3:
            return fn()
        a, k = self._eval(n[2], e)
        return fn(*a, **k)

    def _e_arguments(self, n, e):
        arity(n, 1, 2)
        return self._eval(n[0], e)

    def _e_argument_list(self, n, e):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self._eval(n[off], e)
            if len(v) == 1:
                a.append(v[0])
            elif v[0] in k:
                raise ValueError("already set", n[off])
            elif v[0].startswith("$"):
                e.set_cc(v[0], v[1])
            else:
                k[v[0]] = v[1]
            off += 2
        return a, k

    def _e_argument(self, n, e):
        if len(n) == 1:
            return (self._eval(n[0], e),)
        else:
            arity(n, 3)
            return (
                n[0].value,
                self._eval(n[2], e),
            )

    def _e_add_args(self, n, e):
        if len(n) == 2:
            return lambda x: x()
        arity(n, 3)
        a, k = self._eval(n[1], e)
        return lambda x: x(*a, **k)

    def _e_parameters(self, n, e):
        arity(n, 1, 2)
        return self._eval(n[0], e)

    def _e_parameter_list(self, n, e):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self._eval(n[off], e)
            if len(v) == 1:
                a.append(v[0])
            elif v[0] in k:
                raise ValueError("already set", n[off])
            else:
                k[v[0]] = v[1]
            off += 2
        return a, k

    def _e_parameter(self, n, e):
        if len(n) == 1:
            return (n[0].value,)
        else:
            arity(n, 3)
            return (
                n[0].value,
                self._eval(n[2], e),
            )

    def _e_mod_inst_child(self, n, e):
        if len(n) == 1:
            return self._eval(n[0], e)
        arity(n, 2)

        dd = { "_e_children": n[1] }
        e = Env(parent=e, init=dd)
        return self._eval(n[0], e)

    def _e_no_child(self, n, e):
        return None

    def _e_EOF(self, n, e):
        return None

    def _e_statement(self, n, e):
        arity(n, 1)
        n = n[0]
        if n.rule_name not in {"assignment", "stmt_decl_mod", "stmt_decl_fn"}:
            if self.defs:
                return
        else:
            if not self.defs:
                return
        return self._eval(n, e)

    def _e_child_statement(self, n, e):
        arity(n, 1)
        return self._eval(n[0], e)

    def _e_pr_true(self, n, e):
        return True

    def _e_pr_false(self, n, e):
        return False

    def _e_pr_undef(self, n, e):
        return None

    def _e_mod_inst_bang(self, n, e):
        "!foo: isolated"
        warnings.warn("Object isolation is not yet supported")
        return self._eval(n[1], e)

    def _e_mod_inst_hash(self, n, e):
        "#foo: highlighted"
        warnings.warn("Object highlighting is not yet supported")
        return self._eval(n[1], e)

    def _e_mod_inst_perc(self, n, e):
        "%foo: transparent"
        warnings.warn("Object transparency is not yet supported")
        return self._eval(n[1], e)

    def _e_mod_inst_star(self, n, e):
        "*foo: disabled"
        return None

    def _e_child_statements(self, n, e):
        return self._e__list(n, e)

    _e_primary = _e__descend
    _e_module_instantiation = _e__descend
    _e_vector_element = _e__descend
    _e_expr = _e__descend
    _e_addon = _e__descend

    def eval(self, node=None, env: Env = None):
        """Evaluates a (sub)tree.

        @node: the tree to process
        @env: the environment to use
        """
        if env is None:
            env = self.env
        return self._eval(node or self.nodes, env)
