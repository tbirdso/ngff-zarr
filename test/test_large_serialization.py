from ngff_zarr import to_ngff_image, to_ngff_zarr, to_multiscales, config
from zarr.storage import MemoryStore

from dask_image import imread

from ._data import input_images, store_new_multiscales, verify_against_baseline


def test_large_image_serialization(input_images):
    config.memory_limit = int(1e6)

    dataset_name = "lung_series"
    data = imread.imread(input_images[dataset_name])
    image = to_ngff_image(data=data,
                          dims=('z', 'y', 'x'),
                          scale={'z': 2.5, 'y': 1.40625, 'x': 1.40625},
                          translation={'z': 332.5, 'y': 360., 'x': 0.0},
                          name='LIDC2')
    multiscales = to_multiscales(image)
    baseline_name = "auto/memory_limit_1e6.zarr"
    # store_new_multiscales(dataset_name, baseline_name, multiscales)
    test_store =  MemoryStore(dimension_separator='/')
    to_ngff_zarr(test_store, multiscales)
    # verify_against_baseline(dataset_name, baseline_name, multiscales)