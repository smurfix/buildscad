"""
Command-line interpreter for openscadq
"""
from __future__ import annotations

from .main import process

import click
from build123d import export_step as exp


@click.command
@click.option(
    "-i",
    "--input",
    "infile",
    required=True,
    type=click.Path(dir_okay=False, readable=True, exists=True),
)
@click.option(
    "-o",
    "--output",
    "outfile",
    required=True,
    type=click.Path(dir_okay=False, writable=True, readable=False),
)
@click.option("-d", "--debug", is_flag=True)
@click.option(
    "-p", "--preload", type=click.Path(dir_okay=False, readable=True), multiple=True, help="",
)
def main(infile, outfile, debug, preload):
    "interpret OpenSCAD, emit STEP"
    res = process(infile, debug=debug, preload=preload)
    if res is None:
        print("No output.")
    else:
        if isinstance(res, list):
            rr, res = res, None
            for r in rr:
                if res is None:
                    res = r
                else:
                    res += r
        exp(res, str(outfile))


if __name__ == "__main__":
    main()
