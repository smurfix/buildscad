"""
Evaluate a parsed OpenSCAD file.
"""
from __future__ import annotations

import logging
import math
import sys
import warnings
from functools import partial
from pathlib import Path

from . import env
from .peg import Parser
from .work import Env, ForStep, MainEnv, EnvEval

from arpeggio import ParseTreeNode as Node
from build123d.topology import Compound
from simpleeval import simple_eval

logger = logging.getLogger(__name__)

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


def _skip1(fn):
    fn.skip1 = True
    return fn


class Function:
    """Wrapper for function calls"""

    def __init__(self, evl: Eval, name: str, params: Node, body: Node):
        self.evl = evl
        self.name = name
        self.params = params
        self.body = body

    def _collect(self, *a, **kw):
        "function call; apply arguments and interpret the body"
        p = dict(**self.params[1])
        _env = env.get()

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

        e = Env(name=self.name, parent=self.evl.env, vars_dyn=_env.vars_dyn)
        for k, v in p.items():
            e[k] = v
        return e

    def __call__(self, *a, **kw):
        e = self._collect(*a, **kw)
        return Eval(e).eval(self.body)


class Module(Function):
    """Wrapper for method calls"""

    def __call__(self, *a, **kw):
        e = self._collect(*a, **kw)
        ee = Eval(e)
        ee._children = e["_e_children"] = []
        ee.eval(self.body)
        return ee.union()


class Shape:
    """Stores a statement, presumably one whole evaluation results in a
    shape.
    """

    def __init__(self, evl: Eval, n: Node):
        self.evl = evl
        self.n = n

    def __call__(self):
        return self.evl.eval(self.n)


class EvalVar:
    """Holds the expression for a variable.

    On first call, replaces the var with its evaluation.
    This way we have (a) delayed evaluation and (b) don't
    need to enforce ordering on our OpenSCAD input.
    """

    def __init__(self, evl: Eval, name: str, n: Node):
        self.evl = evl
        self.name = name
        self.n = n
        self.working = False

    def __call__(self):
        if self.working:
            raise ValueError(f"Recursive value for {self.name}")
        self.working = True
        try:
            val = self.evl.eval(self.n)
        finally:
            self.working = False
        self.evl.env.set(self.name, val)
        return val


class Eval:
    """An Evaluator that steps through a block's parse tree and, well,
    evaluates it. This is a two-phase process.

    The first phase processes include statements and collects (but does
    not evaluate) variable assignments, function and module declarations,
    and statements that might actually render something. It is started by
    the top-level ``Input`` node, or in the body of a child statement.

    The second phase traverses the render statements, evaluates them, and
    returns an object (or, if required, a list of objects).
    """

    def __init__(self, env: Env | None = None, debug: bool = False):
        if env is None:
            env = MainEnv()
        self.env = env
        self.debug = debug
        self.level = 0

    def set(self, k, v):
        """(forcibly) set a value"""
        self.env.vars.set(k, v)

    def eval(self, n):
        while True:
            try:
                p = getattr(self, f"_e_{n.rule_name}")
                if self.debug:
                    print(" " * self.level, ">", n.rule_name)

            except AttributeError:
                if not n.rule_name:
                    raise RuntimeError("trying to interpret a terminal element", n) from None
                print(n.tree_str(), file=sys.stderr)
                raise RuntimeError(f"Syntax not implemented: {n.rule_name}")

            else:
                try:
                    if len(n) == 1 and hasattr(p, "skip1"):
                        n = n[0]
                        continue
                except TypeError:
                    pass
            break

        self.level += 1
        try:
            res = p(n)
        except ArityError:
            print(f"ParamCount: {n.rule_name}", file=sys.stderr)
            print(n.tree_str(), file=sys.stderr)
            raise
        finally:
            self.level -= 1

        if self.debug:
            print(" " * self.level, "<", res)

        return res

    def _e_Input(self, n):
        "top level"
        self._children = self.env["_e_children"] = []
        self._e__list(n)

    def _e__list(self, n):
        res = None
        for nn in n:
            self.eval(nn)

    def _e_Include(self, n):
        """'include' statement.

        Adds the file as if it was textually included, except that
        variables from the included file can be overridden.
        """
        # We do this by hooking up the included file as a parent
        # environment.
        arity(n, 2)
        p = Parser(debug=False, reduce_tree=False)
        fn = n[1].value[1:-1]
        try:
            fn = self.env["_path"].parent / fn
        except AttributeError:
            fn = Path(fn)
        tree = p.parse(fn.read_text())
        ep = Env(parent=self.env, name=str(fn))
        res = Eval(ep).eval(tree)
        e.inject_vars(ep)
        return res

    def _e_Use(self, n):
        """'use' statement.

        Add the variables and functions defined by the used module (but
        *not* those it itself imports via 'use'!) to the current scope.
        """
        arity(n, 2)
        p = Parser(debug=False, reduce_tree=False)
        fn = n[1].value[1:-1]
        try:
            fn = self.env["_path"].parent / fn
        except AttributeError:
            fn = Path(fn)

        tree = p.parse(fn.read_text())

        ep = MainEnv(name=str(fn))
        Eval(ep).eval(tree)
        self.env.inject_vars(ep)

    @_skip1
    def _descend(self, n):
        arity(n, 1)
        return self.eval(n[0])

    def _e_stmt_obj(self, n):
        # a top-level statement that creates an object
        arity(n, 1)
        self._children.append(n[0])

    def _e_stmt_list(self, n):
        # top-level block
        e = self.sub(True)
        for nn in n[1:-1]:
            e.eval(nn)
        return e.union()

    def sub(self, children=False):
        e = Eval(Env(parent=self.env))
        if children:
            e._children = e.env["_e_children"] = []
        return e

    def union(self, nodes: list[Node] | None = None):
        if nodes is None:
            nodes = self._children
        # ln = len(self._children) if self._children else 0
        res = None
        for n in nodes:
            r = self.eval(n)
            if r is None:
                continue
            elif res is None:
                res = r
            else:
                res += r

        # assert ln == len(self._children) if self._children else 0, (n,self._children)
        return res

    def _e_explicit_child(self, n):
        ev = self.sub()
        ev.eval(n[1])
        assert not self._children
        self._children = ev._children

    def _e_pr_vec_empty(self, n):
        return ()

    def _e_pr_vec_elems(self, n):
        return self.eval(n[1])

    def _e_vector_elements(self, n):
        res = []
        off = 0
        while off < len(n):
            res.append(self.eval(n[off]))
            off += 2
        return res

    @_skip1
    def _e_expr_case(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        arity(n, 5)
        if res:
            return self.eval(n[2])
        else:
            return self.eval(n[4])

    @_skip1
    def _e_logic_or(self, n):
        res = self.eval(n[0])
        off = 1
        while len(n) > off:
            if res:
                return res
            if n[off].value == "||":
                res = self.eval(n[off + 1])
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    @_skip1
    def _e_logic_and(self, n):
        res = self.eval(n[0])
        off = 1
        while len(n) > off:
            if not res:
                return res
            if n[off].value == "&&":
                res = self.eval(n[off + 1])
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    def _e_equality(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self.eval(n[off + 1])
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

    def _e_comparison(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self.eval(n[off + 1])
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

    @_skip1
    def _e_addition(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self.eval(n[off + 1])
            if n[off].value == "+":
                res += res2
            elif n[off].value == "-":
                res -= res2
            else:
                raise ValueError("Unknown op", n[off])
            off += 2
        return res

    @_skip1
    def _e_multiplication(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self.eval(n[off + 1])
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

    @_skip1
    def _e_unary(self, n):
        arity(n, 1, 2)
        res = self.eval(n[-1])
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

    @_skip1
    def _e_exponent(self, n):
        res = self.eval(n[0])
        if len(n) == 1:
            return res
        arity(n, 3)
        exp = self.eval(n[2])
        if n[1].value == "^":
            return math.pow(res, exp)
        else:
            raise ValueError("Unknown op", n[1])

    def _e_call(self, n):
        res = self.eval(n[0])
        off = 1
        if off < len(n):
            with self.env.cc(res):
                app = self.eval(n[off])
                res = app(self.env.current_call or res)
            off += 1
        while off < len(n):
            app = self.eval(n[off])
            res = app(res)
            off += 1
        return res

    def _e_pr_Num(self, n):
        val = n.value
        try:
            return int(val)
        except ValueError:
            return float(val)

    def _e_pr_Sym(self, n):
        return self.env[n.value]

    @_skip1
    def _e_pr_paren(self, n):
        return self.eval(n[1])

    def _e_pr_Str(self, n):
        return simple_eval(n.value)

    def _e_assignment(self, n):
        self.env[n[0].value] = EnvEval(n[2])

    def _e_stmt_decl_fn(self, n):
        arity(n, 7, 8)
        name = n[1].value
        if len(n) == 8:
            params = self.eval(n[3])
        else:
            params = ((), {})
        body = n[-2]
        self.env[name] = Function(self, name, params, body)

    def _e_stmt_decl_mod(self, n):
        arity(n, 5, 6)
        name = n[1].value
        if name in self.env:
            logger.warning(f"Redefined: {name}")
            return  # already defined

        if len(n) == 6:
            params = self.eval(n[3])
        else:
            params = ((), {})
        body = n[-1]
        self.env[name] = Module(self, name, params, body)

    def _e_lce_for(self, n):
        raise ValueError("'for' in list comprehension is not implemented")

    def _e_lce_for3(self, n):
        raise ValueError("'for' in list comprehension is not implemented")

    def _e_lce_let(self, n):
        raise ValueError("'let' in list comprehension is not implemented")

    def _e_lce_if(self, n):
        raise ValueError("'if' in list comprehension is not implemented")

    def _e_pr_for2(self, n):
        return ForStep(n[1], n[3], 1)

    def _e_pr_for3(self, n):
        return ForStep(n[1], n[3], n[5])

    def _e_fn_call(self, n):
        if self.debug:
            print(" " * self.level, "=", n)

        arity(n, 3, 4)

        try:
            fn = self.env[n[0].value]
        except AttributeError:
            raise ValueError(f"Function {n[0].value !r} undefined") from None
        if len(n) == 3:
            return fn()
        e = self.sub()
        a, k = e.eval(n[2])
        return fn(*a, **k)

    def _e_arguments(self, n):
        arity(n, 1, 2)
        return self.eval(n[0])

    def _e_argument_list(self, n):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self.eval(n[off])
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

    def _e_argument(self, n):
        if len(n) == 1:
            return (self.eval(n[0]),)
        else:
            arity(n, 3)
            return (
                n[0].value,
                self.eval(n[2]),
            )

    def _e_add_args(self, n):
        if len(n) == 2:
            return lambda x: x()
        arity(n, 3)
        a, k = self.eval(n[1])
        return lambda x: x(*a, **k)

    def _e_add_index(self, n):
        if len(n) == 2:
            return lambda x: x()
        arity(n, 3, 999)

        i = 1
        idx = []
        while i < len(n):
            a = self.eval(n[1])
            i += 2
            idx.append(a)

        def ind(idx, x):
            for i in idx:
                x = x[i]
            return x

        return partial(ind, idx)

    @_skip1
    def _e_parameters(self, n):
        arity(n, 1, 2)
        return self.eval(n[0])

    def _e_parameter_list(self, n):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self.eval(n[off])
            if len(v) == 1:
                a.append(v[0])
            elif v[0] in k:
                raise ValueError("already set", n[off])
            else:
                k[v[0]] = v[1]
            off += 2
        return a, k

    def _e_parameter(self, n):
        if len(n) == 1:
            return (n[0].value,)
        else:
            arity(n, 3)
            return (
                n[0].value,
                self.eval(n[2]),
            )

    def _e_mod_inst_child(self, n):
        if len(n) == 1:
            return self.eval(n[0])
        arity(n, 2)

        dd = {"_e_children": n[1]}
        e = Env(parent=self.env, init=dd)
        return Eval(e).eval(n[0])

    def _e_no_child(self, n):
        return None

    def _e_EOF(self, n):
        return None

    def _e_statement(self, n):
        arity(n, 1)
        n = n[0]
        res = self.eval(n)
        if isinstance(res, Compound) and res._dim is None:
            raise RuntimeError("Dimension problem", n)
        return res

    @_skip1
    def _e_child_statement(self, n):
        arity(n, 1)
        return self.eval(n[0])

    def _e_pr_true(self, n):
        return True

    def _e_pr_false(self, n):
        return False

    def _e_pr_undef(self, n):
        return None

    def _e_mod_inst_bang(self, n):
        "!foo: isolated"
        warnings.warn("Object isolation is not yet supported")
        return self.eval(n[1])

    def _e_mod_inst_hash(self, n):
        "#foo: highlighted"
        warnings.warn("Object highlighting is not yet supported")
        return self.eval(n[1])

    def _e_mod_inst_perc(self, n):
        "%foo: transparent"
        warnings.warn("Object transparency is not yet supported")
        return self.eval(n[1])

    def _e_mod_inst_star(self, n):
        "*foo: disabled"
        return None

    def _e_child_statements(self, n):
        return self._e__list(n)

    def _e_ifelse_statement(self, n):
        n = n[0]
        arity(n, 5, 7)
        res = self.eval(n[2])
        if res:
            return self.eval(n[4])
        elif len(n) < 7:
            return None
        else:
            return self.eval(n[6])

    _e_primary = _descend
    _e_module_instantiation = _descend
    _e_vector_element = _descend
    _e_expr = _descend
    _e_addon = _descend
    _e_statement = _descend
