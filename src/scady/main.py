from pathlib import Path
from .peg import Parser
from .eval import Eval
from arpeggio import visit_parse_tree

def process(f: Path, debug:bool = False):
    p = Parser(debug=debug, reduce_tree=False)
    pt = p.parse(f.read_text())
    e = Eval(pt)
    result = e.eval()
    return result



