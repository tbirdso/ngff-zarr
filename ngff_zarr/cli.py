#!/usr/bin/env python

import sys
import argparse
from pathlib import Path

from rich.progress import Progress as RichProgress, SpinnerColumn, TimeElapsedColumn
from rich.console import Console
from zarr.storage import DirectoryStore

if __name__ == "__main__" and __package__ is None:
    __package__ = "ngff_zarr"

from .ngff_image import NgffImage
from .to_multiscales import to_multiscales
from .to_ngff_zarr import to_ngff_zarr
from .cli_input_to_ngff_image import cli_input_to_ngff_image
from .detect_cli_input_backend import detect_cli_input_backend, conversion_backends_values
from .rich_dask_progress import RichDaskProgress
from rich import print as rprint

def main():
    parser = argparse.ArgumentParser(description='Convert datasets to and from the OME-Zarr Next Generation File Format.')
    parser.add_argument('input', nargs='+', help='Input image(s)')
    parser.add_argument('output', help='Output image. Just print information with "info"')
    parser.add_argument('-q', '--quiet', action='store_true', help='Do not display progress information')
    parser.add_argument('--input-backend', choices=conversion_backends_values, help='Input conversion backend')

    args = parser.parse_args()

    if args.input_backend is None:
        input_backend = detect_cli_input_backend(args.input)
    else:
        input_backend = ConversionBackend(args.input_backend)

    if args.output != "info":
        output_store = DirectoryStore(args.output, dimension_separator='/')

    if args.quiet:
        ngff_image = cli_input_to_ngff_image(input_backend, args.input)
        multiscales = to_multiscales(ngff_image)
        if args.output == "info":
            rprint(multiscales)
            return
        to_ngff_zarr(output_store, multiscales)
    else:
        console = Console()

        with RichProgress(SpinnerColumn(), *RichProgress.get_default_columns(),
                TimeElapsedColumn(), console=console, transient=False,
                redirect_stdout=True, redirect_stderr=True) as progress:
            rich_dask_progress = RichDaskProgress(progress)
            rich_dask_progress.register()

            ngff_image = cli_input_to_ngff_image(input_backend, args.input)
            multiscales = to_multiscales(ngff_image, progress=rich_dask_progress)
            if args.output == "info":
                console.log(multiscales)
                return
            to_ngff_zarr(output_store, multiscales, progress=rich_dask_progress)

if __name__ == '__main__':
    main()
