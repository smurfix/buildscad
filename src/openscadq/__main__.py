"""
Command-line interpreter for openscadq
"""
from __future__ import annotations

from pathlib import Path

from .main import process

import click
from cadquery import exporters as exp


@click.command
@click.option("-i", "--input", "infile", required=True, type=Path)
@click.option("-o", "--outputput", "outfile", required=True, type=Path)
@click.option("-d", "--debug", is_flag=True)
@click.option("-p", "--preload", type=click.Path(dir_okay=False,readable=True),multiple=True,help="")
def main(infile, outfile, debug, preload):
    "interpret OpenSCAD, emit STEP"
    res = process(infile, debug=debug, preload=preload)
    if res is None:
        print("No output.")
    else:
        exp.export(res, str(outfile))


if __name__ == "__main__":
    main()
