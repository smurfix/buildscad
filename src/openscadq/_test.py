from __future__ import annotations

from pathlib import Path
from subprocess import run as spawn, DEVNULL
import io
from tempfile import NamedTemporaryFile
from contextlib import suppress

from openscadq import parse
from build123d import Mesher, Shape

class Res:
    tolerance = 0.001
    def __init__(self):
        self._models = {}
    def add(self, name, model):
        if model is None:
            return
        self._models[name] = model
    @property
    def models(self):
        for k,v in self._models.items():
            yield (v,k)
    def __getitem__(self, x):
        return self._models[x]
    def __contains__(self, x):
        return x in self._models
    def __len__(self):
        return len(self._models)

def testcase(i):
    import tests.env_openscad as _env
    result = Res()
    params = {}
    run=True

    pyf = Path(f"tests/models/{i :03d}.py")
    if pyf.exists():
        py = pyf.read_text()
        pyc = compile(py, str(pyf), "exec")
        env2 = {}
        exec(pyc, _env.__dict__, env2)

        with suppress(KeyError):
            result.volume = env2["volume"]
        with suppress(KeyError):
            result.tolerance = env2["tolerance"]
        with suppress(KeyError):
            params = env2["params"]
        with suppress(KeyError):
            run = env2["run"]

        try:
            m2 = env2["work"]
        except KeyError:
            res = None
            for v in env2.values():
                if not isinstance(v,Shape) or v._dim != 3:
                    continue
                if res is None:
                    res = v
                else:
                    res += v
            assert res, "No Python results. Did you assign them to something?"
            m2 = res
        else:
            m2 = m2(**params)
        result.add("python",m2)

    scadf = f"tests/models/{i :03d}.scad"
    env1 = parse(scadf)
    try:
        m1 = env1["work"]
    except KeyError:
        # Oh well. Gather toplevel elements instead.
        from openscadq.eval import Eval

        ev = Eval(env1)
        m1 = ev.union(env1["_e_children"])
    else:
        m1 = m1(**params)
    result.add("parser", m1)

 
    if run:
        with NamedTemporaryFile(suffix=".stl") as tf,NamedTemporaryFile(suffix=".txt") as out:
            spawn(["openscad","--export-format=binstl", "-o",tf.name,scadf], check=True, stdin=DEVNULL, stdout=out, stderr=out, text=True)
            m3 = Mesher().read(tf.name)
            res = None
            for m in m3:
                if res is None:
                    res = m
                else:
                    res += m

            result.add("openscad",res)


    return result
