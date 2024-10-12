"""
Command-line interpreter for openscadq
"""
from __future__ import annotations

from pathlib import Path

from .main import process

import click
from cadquery import exporters as exp


@click.command
@click.option("-i", "--input", "infile", required=True, type=click.Path(dir_okay=False, readable=True, exists=True))
@click.option("-o", "--output", "outfile", required=True, type=click.Path(dir_okay=False, writable=True, readable=False))
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
