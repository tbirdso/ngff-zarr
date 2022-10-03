from ngff_zarr import itk_image_to_ngff_image
import itk
import numpy as np

from ._data import input_images, test_data_dir


def test_2d_image(input_images):
    itk_image = itk.imread(test_data_dir / "input" / "cthead1.png")
    ngff_image = itk_image_to_ngff_image(itk_image)
    assert np.array_equal(np.asarray(itk_image), np.asarray(ngff_image.data))
    assert ngff_image.dims == ("y", "x")
    assert ngff_image.scale["x"] == 1.0
    assert ngff_image.scale["y"] == 1.0
    assert ngff_image.translation["x"] == 0.0
    assert ngff_image.translation["y"] == 0.0
    assert ngff_image.name == "image"
    assert ngff_image.axes_units == None