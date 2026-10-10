"""Raster grid geometry shared by every layer of a scene."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

UTM43N = "EPSG:32643"  # covers Delhi (72 to 78 E)


@dataclass(frozen=True, slots=True)
class Grid:
    """A north-up raster: row 0 is the northern edge, column 0 the western edge."""

    x0: float  # easting of the north-west corner, metres
    y0: float  # northing of the north-west corner, metres
    pixel_size: float
    rows: int
    cols: int
    crs: str = UTM43N

    @property
    def shape(self) -> tuple[int, int]:
        return (self.rows, self.cols)

    @property
    def transform(self) -> tuple[float, float, float, float, float, float]:
        """GDAL-style affine (a, b, c, d, e, f) as used by rasterio.Affine."""
        return (self.pixel_size, 0.0, self.x0, 0.0, -self.pixel_size, self.y0)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(minx, miny, maxx, maxy) in the grid CRS."""
        return (
            self.x0,
            self.y0 - self.rows * self.pixel_size,
            self.x0 + self.cols * self.pixel_size,
            self.y0,
        )

    def to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Map coordinates to fractional (row, col)."""
        return ((self.y0 - y) / self.pixel_size, (x - self.x0) / self.pixel_size)

    def to_map(self, row: float, col: float) -> tuple[float, float]:
        """Fractional (row, col) to map coordinates of that point."""
        return (self.x0 + col * self.pixel_size, self.y0 - row * self.pixel_size)

    def cell_centres(self) -> tuple[np.ndarray, np.ndarray]:
        """Map coordinates (x, y) of every cell centre, each shaped like the grid."""
        cols = self.x0 + (np.arange(self.cols) + 0.5) * self.pixel_size
        rows = self.y0 - (np.arange(self.rows) + 0.5) * self.pixel_size
        xs, ys = np.meshgrid(cols, rows)
        return xs, ys
