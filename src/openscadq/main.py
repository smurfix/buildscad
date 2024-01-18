from pathlib import Path
from .peg import Parser
from .eval import Eval
from .work import MainEnv
from arpeggio import visit_parse_tree

def process(f: Path, debug:bool = False, write_once:bool = True, **vars):
    p = Parser(debug=debug, reduce_tree=False)
    tree = p.parse(f.read_text())
    env = MainEnv(write_once=write_once)
    for k,v in vars.items():
        env.set(k,v)

    e = Eval(tree, env=env)
    result = e.eval()
    return result



