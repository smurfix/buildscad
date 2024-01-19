from __future__ import annotations

from pathlib import Path

from .main import process

import click
from cadquery import exporters as exp


@click.command
@click.option("-i", "--input", "infile", required=True, type=Path)
@click.option("-o", "--outputput", "outfile", required=True, type=Path)
@click.option("-d", "--debug", is_flag=True)
def main(infile, outfile, debug):
    res = process(infile, debug=debug)
    if res is None:
        print("No output.")
    else:
        exp.export(res, str(outfile))


if __name__ == "__main__":
    main()
