# ngff-zarr

[![PyPI - Version](https://img.shields.io/pypi/v/ngff-zarr.svg)](https://pypi.org/project/ngff-zarr)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ngff-zarr.svg)](https://pypi.org/project/ngff-zarr)
[![Test](https://github.com/thewtex/ngff-zarr/actions/workflows/test.yml/badge.svg)](https://github.com/thewtex/ngff-zarr/actions/workflows/test.yml)

-----

A lean and kind Open Microscopy Environment (OME) Next Generation File Format (NGFF) Zarr implementation.

**Table of Contents**

- [Installation](#installation)
- [Features](#features)
- [Usage](#usage)
- [See also](#see-also)
- [License](#license)

## Installation

To install the command line interface (CLI):

```console
pip install 'ngff-zarr[cli]'
```

## Features

- Minimal dependencies
- Work with arbitrary Zarr store types
- Lazy, parallel, and web ready -- no local filesystem required
- Process extremely large datasets
- Multiple downscaling methods
- Supports Python>=3.7


## Usage

### Convert an image file

Convert any scientific image file format supported by either [itk](https://wasm.itk.org/docs/image_formats), [tifffile](https://pypi.org/project/tifffile/), or [imageio](https://imageio.readthedocs.io/en/stable/formats/index.html).

Example:

```console
ngff-zarr -i ./MR-head.nrrd -o ./MR-head.zarr
```

Convert an image file series (note the quotes):

```console
ngff-zarr -i "series/*.tif" -o ome-ngff.zarr
```

Print information about generated multiscales:

```console
ngff-zarr -i "series/*.tif"
```

More options:

```console
ngff-zarr --help
```

## See also

- [ome-zarr-py](https://github.com/ome/ome-zarr-py)
- [multiscale-spatial-image](https://github.com/spatial-image/multiscale-spatial-image)

## License

`ngff-zarr` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Development

Contributions are welcome and appreciated.

To run the unit tests:

```sh
pip install -e ".[test,dask-image,itk,cli]"
pytest
```

### Updating test data

1. Generate new test data tarball

```
cd test/data
tar cvf ../data.tar baseline input
gzip -9 ../data.tar
```

2. Upload the data to [web3.storage](https://web3.storage)

3. Upload the `test_data_ipfs_cid` (from web3.storage web UI) and `test_data_sha256` (`sh256sum ../data.tar.gz`) variables in *test/_data.py*.
