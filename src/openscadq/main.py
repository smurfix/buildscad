from __future__ import annotations

from pathlib import Path

from .eval import Eval
from .peg import Parser
from .work import MainEnv


def process(f: Path, debug: bool = False, **vars):
    p = Parser(debug=debug, reduce_tree=False)
    tree = p.parse(f.read_text())
    env = MainEnv()
    for k, v in vars.items():
        env.set(k, v)

    e = Eval(tree, env=env)
    result = e.eval()
    return result
