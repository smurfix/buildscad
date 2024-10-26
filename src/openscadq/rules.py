"""
Rules for parsing OpenSCAD.
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

@_skip1
def _descend(self, n):
    arity(n, 1)
    return self.eval(n[0])

class _CommonRules:
    def _e__list(self, n):
        res = None
        for nn in n:
            self.eval(nn)

class _StaticRules(_CommonRules):
    def _e_Input(self, n):
        "top level"
        self._e__list(n)

    _e_statement = _descend
    _e_module_instantiation = _descend

    def _e_assignment(self, n):
        name = n[0].value
        self.add_var(name, n[2])

    def _e_stmt_obj(self, n):
        # a top-level statement that creates an object
        arity(n, 1)
        stmt = self.eval(n[0])
        if stmt is None:
            breakpoint()
            stmt = self.eval(n[0])
            raise RuntimeError("Empty statement")
        self.work.append(stmt)

    def _e_stmt_decl_fn(self, n):
        arity(n, 7, 8)
        name = n[1].value
        if name in self.funcs:
            logger.warning(f"Redefined: {name}")
            return  # already defined

        if len(n) == 8:
            params = self.eval(n[3])
        else:
            params = ((), {})
        body = n[-2]
        self.funcs[name] = Function(self, name, params, body)

    def _e_stmt_decl_mod(self, n):
        arity(n, 5, 6)
        name = n[1].value
        if name in self.mods:
            logger.warning(f"Redefined: {name}")
            return  # already defined

        if len(n) == 6:
            params = self.eval(n[3])
        else:
            params = ((), {})

        nn = n[-1]

        # avoid wrapping `module foo() {…}` with two nested environments
        assert nn.rule_name == "statement"
        assert nn[0].rule_name == "stmt_obj"
        if nn[0][0].rule_name == "stmt_list":
            body = self._encap_list(nn[0][0][1:-1])
        else:
            body = StaticEnv(self)
            body.eval(nn)
        self.mods[name] = Module(name, params, body)

    def _e_explicit_child(self, n):
        # foo() { … }
        arity(n,3)
        return self._encap_list(n[1])

    def _e_child_statement(self, n) -> None:
        # a child statement that creates an object
        arity(n, 1)
        stmt = self.eval(n[0])
        if stmt is not None:
            self.work.append(stmt)

    def _e_child_statements(self, n):
        e = StaticEnv(self)
        for nn in n:
            e.eval(nn)
        return e

    def _encap_list(self, n):
        # block: '{' … '}'
        e = StaticEnv(self)
        for nn in n:
            e.eval(nn)
        return e

    def _e_stmt_list(self, n):
        return self._encap_list(n[1:-1])

    def _e_no_child(self, n):
        return None

    def _e_mod_inst_child(self, n):
        # foo() { … }
        # foo() bar() …
        # foo();
        arity(n, 1, 2)
        if len(n) == 1:
            return Statement(self, n[0])

        # These dances are necessary to ensure that the actual child
        # environment isn't wrapped, which would prevent access to
        # the individual parts.
        assert n[1].rule_name == "child_statement"
        assert len(n[1]) == 1
        if n[1][0].rule_name == "no_child":
            return Statement(self, n[0])
        elif n[1][0].rule_name == "explicit_child":
            child = self._encap_list(n[1][0][1])
            if not child.work:
                return Statement(self, n[0])
        else:
            assert n[1][0].rule_name == "module_instantiation"
            child = StaticEnv(self)
            child.work.append(child.eval(n[1][0]))

        return ParentStatement(self, n[0], child)

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

    def _e_mod_call(self, n):
        arity(n, 3, 4)
        return Statement(self, n)

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
    def _e_EOF(self, n):
        pass


class _DynRules(_CommonRules):
    def _e_mod_call(self, n):
        name = n[0].value
        if len(n) == 3:
            a,k = (),{}
        else:
            a, k = self.eval(n[2])
        return self.mod(name, *a, **k)

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

    def _e_expr_fn(self, n):
        # build a function object
        arity(n,4,5)
        if len(n) == 5:
            params = self.eval(n[2])
        else:
            params = ((), {})
        body = n[-1]
        return Function(self.static, "‹noname›", params, body)


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

    @_skip1
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

    @_skip1
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
        # Special case: call a named function
        off = 1
        if n[0][0].rule_name == "pr_Sym" and len(n) > 1 and n[1][0].rule_name == "add_args":
            args = n[1][0]
            if len(args) == 2:
                a, k = (),{}
            else:
                a, k = self.eval(n[1])
            res = self.func(n[0][0].value, *a, **k)
            off += 1
        else:
            res = self.eval(n[0])

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
        return self.var(n.value)

    @_skip1
    def _e_pr_paren(self, n):
        return self.eval(n[1])

    def _e_pr_Str(self, n):
        return simple_eval(n.value)

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

    def _e_pr_true(self, n):
        return True

    def _e_pr_false(self, n):
        return False

    def _e_pr_undef(self, n):
        return None

    _e_expr = _descend
    _e_primary = _descend
    _e_vector_element = _descend
    _e_addon = _descend

class XXX_EvalVar:
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

    def _e_mod_call(self, n):
        if self.debug:
            print(" " * self.level, "=", n)

        arity(n, 3, 4)

        name = n[0].value
        if len(n) == 3: # fn()
            return self.mod(name)

        # fn( … )
        a, k = self.eval(n[2])
        return self.mod(name, *a, **k)


class XXX_Eval:
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

    def sub(self, children=False):
        e = Eval(Env(parent=self.env))
        if children:
            e._children = e.env["_e_children"] = []
        return e

    def union(self) -> Shape|None:
        # ln = len(self._children) if self._children else 0
        res = None
        for n in self.env.work:
            r = self.eval(n)
            if r is None:
                continue
            elif res is None:
                res = r
            else:
                res += r

        # assert ln == len(self._children) if self._children else 0, (n,self._children)
        return res



    def _e_EOF(self, n):
        return None

    def _e_child_statement(self, n):
        arity(n, 1)
        self._children.append(n[0])

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

# annoying recursive imports

from .blocks import Function,Module,Variable,Statement,ParentStatement
from .env import StaticEnv
