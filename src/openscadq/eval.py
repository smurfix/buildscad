import cadquery as cq
from arpeggio import PTNodeVisitor
from .work import Env, MainEnv
from functools import partial
import sys
import math
import warnings

class ArityError(ValueError):
    pass

def arity(n,a,b=None):
    if b is None:
        if len(n) != a:
            raise ArityError(n,a)
    elif not a <= len(n) <= b:
        raise ArityError(n,a,b)

class Function:
    def __init__(self,name,params,body,env):
        self.name = name
        self.params = params
        self.body = body
        self.env = env

    def __call__(self, *a, _env, **kw):
        p = dict(**self.params[1])
        pa = self.params[0]

        p.update(kw)
        off = 0
        for v in a:
            while pa[off] in p:
                off += 1
            p[pa[off]] = v
            off += 1

        e = Eval(nodes=self.body, env=Env(name=self.name, parent=_env, init=p))
        return e.eval()

class Module(Function):
    pass

class Eval:
    def __init__(self, nodes, env:Env|None=None):
        self.nodes = nodes
        if env is None:
            env = MainEnv()
        self.env = env

    def _eval(self, n, e):
        try:
            p = getattr(self,f"_e_{n.rule_name}")
        except AttributeError:
            if not n.rule_name:
                breakpoint()
            print(f"Unknown: {n.rule_name}")
            print(n.tree_str())
            sys.exit(1)
        try:
            return p(n,e)
        except ArityError:
            print(f"ParamCount: {n.rule_name}")
            print(n.tree_str())
            sys.exit(1)

    def _e_Input(self, n, e):
        ws = None
        for nn in n:
            r = self._eval(nn,e)
            if r is None:
                pass
            elif isinstance(r,cq.Workplane):
                if ws is None:
                    ws = cq.Workplane("XY")
                ws = ws.add(r)
            else:
                warnings.warn(f"Unknown result: {r !r}")
        return ws


    def _e__descend(self, n, e):
        arity(n,1)
        return self._eval(n[0], e)

    def _e_stmt_list(self,n,e):
        return self._e_Input(n[1:-1],e)

    def _e_pr_vec_empty(self,n,e):
        return ()

    def _e_pr_vec_elems(self,n,e):
        return self._eval(n[1],e)

    def _e_vector_elements(self,n,e):
        res = []
        off = 0
        while off < len(n):
            res.append(self._eval(n[off],e))
            off += 2
        return res

    def _e_expr_case(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        arity(n,5)
        if res:
            return self._eval(n[2], e)
        else:
            return self._eval(n[4], e)

    def _e_logic_or(self,n,e):
        res = self._eval(n[0], e)
        off = 1
        while len(n) > off:
            if res:
                return res
            if n[off].value == "||":
                res = self._eval(n[off+1], e)
            else:
                raise ValueError("Unknown op",n[off])
            off += 2
        return res

    def _e_logic_and(self,n,e):
        res = self._eval(n[0], e)
        off = 1
        while len(n) > off:
            if not res:
                return res
            if n[off].value == "&&":
                res = self._eval(n[off+1], e)
            else:
                raise ValueError("Unknown op",n[off])
            off += 2
        return res

    def _e_equality(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off+1], e)
            if n[off].value == "==":
                if res != res2:
                    return False
            elif n[off].value == "!=":
                if res == res2:
                    return False
            else:
                raise ValueError("Unknown op",n[off])
            off += 2
            res = res2
        return True

    def _e_comparison(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off+1], e)
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
                raise ValueError("Unknown op",n[off])
            off += 2
            res = res2
        return True

    def _e_addition(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off+1], e)
            if n[off].value == "+":
                res += res2
            elif n[off].value == "-":
                res -= res2
            else:
                raise ValueError("Unknown op",n[off])
            off += 2
        return res

    def _e_multiplication(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        off = 1
        while len(n) > off:
            res2 = self._eval(n[off+1], e)
            if n[off].value == "*":
                res *= res2
            elif n[off].value == "/":
                res /= res2
            elif n[off].value == "%":
                res %= res2
            else:
                raise ValueError("Unknown op",n[off])
            off += 2
        return res

    def _e_unary(self,n,e):
        arity(n,1,2)
        res = self._eval(n[-1], e)
        if len(n) == 2:
            if n[0].value == "+":
                pass
            elif n[0].value == "-":
                res = -res
            elif n[0].value == "!":
                res = not res
            else:
                raise ValueError("Unknown op",n[off])
        return res

    def _e_exponent(self,n,e):
        res = self._eval(n[0], e)
        if len(n) == 1:
            return res
        arity(n,3)
        exp = self._eval(n[2], e)
        if n[1].value == "^":
            return math.pow(res,exp)
        else:
            raise ValueError("Unknown op",n[off])

    def _e_call(self,n,e):
        res = self._eval(n[0], e)
        off = 1
        if off < len(n):
            with e.cc(res):
                app = self._eval(n[off], e)
                res = app(res)
            off += 1
        while off < len(n):
            app = self._eval(n[off], e)
            res = app(res)
            off += 1
        return res

    def _e_pr_Num(self,n,e):
        val = n.value
        try:
            return int(val)
        except ValueError:
            return float(val)

    def _e_pr_Sym(self,n,e):
        return e[n.value]

    def _e_pr_Str(self,n,e):
        return eval(n.value)

    def _e_assignment(self, n, e):
        self.env.vars[n[0].value] = self._eval(n[2], e)

    def _e_stmt_decl_fn(self,n,e):
        arity(n,7,8)
        name = n[1].value
        if len(n) == 8:
            params = self._eval(n[3],e)
        else:
            params = ((),{})
        body = n[-2]
        e.vars[name] = Function(name,params,body,e)

    def _e_stmt_decl_mod(self,n,e):
        arity(n,5,6)
        name = n[1].value
        if len(n) == 6:
            params = self._eval(n[3],e)
        else:
            params = ((),{})
        body = n[5]
        e.vars[name] = Module(name,params,body,e)

    def _e_fn_call(self,n,e):
        arity(n,3,4)
        try:
            fn = e[n[0].value]
        except AttributeError:
            raise ValueError(f"Function {n[0].value !r} undefined") from None
        if len(n) == 3:
            return fn()
        a,k = self._eval(n[2],e)
        return fn(*a,**k)

    def _e_arguments(self,n,e):
        arity(n,1,2)
        return self._eval(n[0], e)

    def _e_argument_list(self,n,e):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self._eval(n[off], e)
            if len(v) == 1:
                a.append(v[0])
            else:
                if v[0] in k:
                    raise ValueError("already set",n[off])
                if v[0].startswith("$"):
                    e.set_cc(v[0], v[1])
                else:
                    k[v[0]] = v[1]
            off += 2
        return a,k

    def _e_argument(self,n,e):
        if len(n) == 1:
            return (self._eval(n[0], e),)
        else:
            arity(n,3)
            return (n[0].value, self._eval(n[2], e),)

    def _e_add_args(self,n,e):
        if len(n) == 2:
            return lambda x:x()
        arity(n,3)
        a,k = self._eval(n[1], e)
        return lambda x:x(*a,**k)

    def _e_parameters(self,n,e):
        arity(n,1,2)
        return self._eval(n[0], e)

    def _e_parameter_list(self,n,e):
        a = []
        k = {}
        off = 0
        while len(n) > off:
            v = self._eval(n[off], e)
            if len(v) == 1:
                a.append(v[0])
            else:
                if v[0] in k:
                    raise ValueError("already set",n[off])
                k[v[0]] = v[1]
            off += 2
        return a,k

    def _e_parameter(self,n,e):
        if len(n) == 1:
            return (n[0].value,)
        else:
            arity(n,3)
            return (n[0].value, self._eval(n[2], e),)

    def _e_mod_inst_child(self,n,e):
        if len(n) == 1:
            return self._eval(n[0], e)

        off = len(n)-1
        res = self._eval(n[off], e)
        while off:
            off -= 1
            res = self._eval(n[off], Env(parent=e, init=dict(_e_children=res)))
        return res

    def _e_no_child(self,n,e):
        return None

    def _e_EOF(self,n,e):
        return None

    _e_statement = _e__descend
    _e_child_statement = _e__descend
    _e_primary = _e__descend
    _e_module_instantiation = _e__descend
    _e_vector_element = _e__descend
    _e_expr = _e__descend
    _e_addon = _e__descend


    def eval(self):
        return self._eval(self.nodes,self.env)

