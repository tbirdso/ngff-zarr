#!/usr/bin/env python

if __name__ == "__main__" and __package__ is None:
    __package__ = "ngff_zarr"

import sys
import argparse
from pathlib import Path
import atexit
import signal
import os

from rich.progress import Progress as RichProgress, SpinnerColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.pretty import Pretty
from rich.spinner import Spinner
from zarr.storage import DirectoryStore
import zarr
import dask.utils

from .ngff_image import NgffImage
from .to_multiscales import to_multiscales
from .to_ngff_image import to_ngff_image
from .to_ngff_zarr import to_ngff_zarr
from .from_ngff_zarr import from_ngff_zarr
from .cli_input_to_ngff_image import cli_input_to_ngff_image
from .ngff_image_to_itk_image import ngff_image_to_itk_image
from .detect_cli_io_backend import detect_cli_io_backend, ConversionBackend, conversion_backends_values
from .methods import Methods, methods_values
from .rich_dask_progress import NgffProgress, NgffProgressCallback
from .zarr_metadata import is_dimension_supported, is_unit_supported
from .config import config

def _multiscales_to_ngff_zarr(live, args, output_store, rich_dask_progress, multiscales):
    if not args.output:
        if args.quiet:
            live.update(Pretty(multiscales))
        else:
            live.update(Panel(Pretty(multiscales), title="[red]NGFF OME-Zarr", subtitle="[red]information", style="magenta"))
        return
    to_ngff_zarr(output_store, multiscales, progress=rich_dask_progress)

def _ngff_image_to_multiscales(live, ngff_image, args, progress, rich_dask_progress, subtitle, method):
    data = ngff_image.data
    if args.dims:
        if len(args.dims) != len(ngff_image.dims):
            live.console.print(f"[red]Provided number of dims do not match expected: {len(ngff_image.dims)}")
            sys.exit(1)
        ngff_image.dims = args.dims
    if args.scale:
        if len(args.scale) % 2 != 0:
            live.console.print(f"[red]Provided scales are expected to be dim value pairs")
            sys.exit(1)
        n_scale_args = len(args.scale) // 2
        for scale in range(n_scale_args):
            dim = args.scale[scale*2]
            value = float(args.scale[scale*2+1])
            ngff_image.scale[dim] = value
    if args.translation:
        if len(args.translation) % 2 != 0:
            live.console.print(f"[red]Provided translations are expected to be dim value pairs")
            sys.exit(1)
        n_translation_args = len(args.translation) // 2
        for translation in range(n_translation_args):
            dim = args.translation[translation*2]
            value = float(args.translation[translation*2+1])
            ngff_image.translation[dim] = value    
    if args.units:
        if len(args.units) % 2 != 0:
            live.console.print(f"[red]Provided units are expected to be dim value pairs, i.e. \"x\" \"meter\" ...")
            sys.exit(1)
        unit_pairs = {str(args.units[unit*2]).lower(): str(args.units[unit*2+1]).lower()
                        for unit in range(len(args.units) // 2)}
        unsupported_units = [value for value in unit_pairs.values() if not is_unit_supported(value)]
        if any(unsupported_units):
            live.console.print(f"[red]The following unit(s) were requested but are not supported: {unsupported_units}")
            sys.exit(1)
        ngff_image.axes_units = unit_pairs
    if args.name:
        ngff_image.name = args.name

    # Generate Multiscales
    cache = data.nbytes > config.memory_target
    if not args.output:
        cache = False
    if not args.quiet:
        live.update(Panel(progress, title="[red]NGFF OME-Zarr", subtitle=subtitle, style="magenta"))
    chunks = args.chunks
    if chunks is not None:
        if len(chunks) == 1:
            chunks = chunks[0]
        else:
            chunks = tuple(chunks)
    multiscales = to_multiscales(ngff_image, method=method, progress=rich_dask_progress, chunks=chunks, cache=cache)
    return multiscales


def main():
    parser = argparse.ArgumentParser(description='Convert datasets to and from the OME-Zarr Next Generation File Format.')
    parser.add_argument('-i', '--input', nargs='+', help='Input image(s)', required=True)
    parser.add_argument('-o', '--output', help='Output image. If not specified just print information to stdout.')

    metadata_group = parser.add_argument_group("metadata", "Specify output metadata")
    metadata_group.add_argument('-d', '--dims', nargs='+', help='Ordered OME-Zarr NGFF dimensions from {"t", "z", "y", "x", "c"}', metavar='DIM')
    metadata_group.add_argument('-u', '--units', nargs='+', help='Ordered OME-Zarr NGFF axes spatial or temporal units', metavar='UNITS')
    metadata_group.add_argument('-s', '--scale', nargs='+', help='Override scale / spacing for each dimension, e.g. z 4.0 y 1.0 x 1.0', metavar='SCALE')
    metadata_group.add_argument('-t', '--translation', nargs='+', help='Override translation / origin for each dimension, e.g. z 0.0 y 50.0 x 40.0', metavar='TRANSLATION')
    metadata_group.add_argument('-n', '--name', help="Image name")
    metadata_group.add_argument('--output-scale', help="Scale to pick from multiscale input for a single-scale output format", type=int, default=0)

    processing_group = parser.add_argument_group("processing", "Processing options")
    processing_group.add_argument('-c', '--chunks', nargs='+', type=int, help='Dask array chunking specification, either a single integer or integer per dimension, e.g. 64 or 8 16 32', metavar='CHUNKS')
    processing_group.add_argument('-m', '--method', default="dask_image_gaussian", choices=methods_values, help="Downsampling method")
    processing_group.add_argument('-q', '--quiet', action='store_true', help='Do not display progress information')
    processing_group.add_argument('-l', '--local-cluster', action='store_true', help='Create a Dask Distributed LocalCluster. Better for large datasets.')
    processing_group.add_argument('--input-backend', choices=conversion_backends_values, help='Input conversion backend')
    processing_group.add_argument('--memory-target', help='Memory limit, e.g. 4GB')
    processing_group.add_argument('--cache-dir', help='Directory to use for caching with large datasets')

    args = parser.parse_args()

    if args.memory_target:
        config.memory_target = dask.utils.parse_bytes(args.memory_target)

    if args.cache_dir:
        cache_dir = Path(args.cache_dir).resolve()
        if not cache_dir.exists():
            os.makedirs(cache_dir)
        config.cache_store = zarr.storage.DirectoryStore(cache_dir,
                dimension_separator='/')

    console = Console()
    progress = RichProgress(SpinnerColumn(), MofNCompleteColumn(), TimeElapsedColumn(), *RichProgress.get_default_columns(), transient=False, console=console)
    rich_dask_progress = None

    # Setup LocalCluster
    if args.local_cluster:
        from dask.distributed import Client, LocalCluster

        n_workers = 4
        worker_memory_target = config.memory_target // n_workers
        try:
            import psutil
            n_workers = psutil.cpu_count(False) // 2
            worker_memory_target = config.memory_target // n_workers
        except ImportError:
            pass

        cluster = LocalCluster(n_workers=n_workers, memory_target=worker_memory_target, processes=True, threads_per_worker=2)
        client = Client(cluster)

        def shutdown_client(sig_id, frame):
            client.shutdown()
        atexit.register(shutdown_client, None, None)
        signal.signal(signal.SIGTERM, shutdown_client)
        signal.signal(signal.SIGINT, shutdown_client)

        if not args.quiet:
            console.log(f"[yellow]Dashboard: [cyan]{client.dashboard_link}")

        if not args.quiet:
            rich_dask_progress = NgffProgress(progress)
    else:
        if not args.quiet:
            rich_dask_progress = NgffProgressCallback(progress)
            rich_dask_progress.register()

    # Parse conversion options
    if args.input_backend is None:
        input_backend = detect_cli_io_backend(args.input)
    else:
        input_backend = ConversionBackend(args.input_backend)
    if args.method is None:
        method = Methods.ITK_GAUSSIAN
    else:
        method = Methods(args.method)

    if args.output:
        output_backend = detect_cli_io_backend([args.output,])
    output_store = None
    if args.output and output_backend is ConversionBackend.NGFF_ZARR:
        output_store = DirectoryStore(args.output, dimension_separator='/')

    subtitle = "[red]generation"
    if not args.output:
        subtitle = "[red]information"
    initial = Panel(Spinner('point', text="Loading input..."), title="[red]NGFF OME-Zarr", subtitle=subtitle, style="magenta")
    if args.quiet:
        initial = None
    with Live(initial, console=console) as live:
        if args.output:
            if output_backend is ConversionBackend.ITK:
                import itk
                ngff_image = cli_input_to_ngff_image(input_backend, args.input, args.output_scale)
                if isinstance(rich_dask_progress, NgffProgressCallback):
                    rich_dask_progress.add_callback_task(f"[green]Converting Zarr Array to NumPy Array")
                itk_image = ngff_image_to_itk_image(ngff_image, wasm=False)
                itk.imwrite(itk_image, args.output)
                return

        if input_backend is ConversionBackend.NGFF_ZARR:
            store = zarr.storage.DirectoryStore(args.input[0])
            multiscales = from_ngff_zarr(store)
            _multiscales_to_ngff_zarr(live, args, output_store, rich_dask_progress, multiscales)
        elif input_backend is ConversionBackend.TIFFFILE:
            try:
                import tifffile
                if len(args.input) == 1:
                    files = args.input[0]
                else:
                    files = args.input
                with tifffile.imread(files, aszarr=True) as store:
                    root = zarr.open(store, mode='r')
                    ngff_image = to_ngff_image(root)
                    multiscales = _ngff_image_to_multiscales(live, ngff_image, args, progress, rich_dask_progress, subtitle, method)
                    _multiscales_to_ngff_zarr(live, args, output_store, rich_dask_progress, multiscales)
            except ImportError:
                print('[red]Please install the [i]tifffile[/i] package.')
                sys.exit(1)
        else:
            # Generate NgffImage
            ngff_image = cli_input_to_ngff_image(input_backend, args.input)
            multiscales = _ngff_image_to_multiscales(live, ngff_image, args,
                    progress, rich_dask_progress, subtitle, method)
            _multiscales_to_ngff_zarr(live, args, output_store, rich_dask_progress, multiscales)

if __name__ == '__main__':
    main()
