"""grid.py — cell_id_for(lat, lon, grid_km) → str (DOC 3 M3).

Equirectangular grid cell assignment.  Deterministic; no dependencies.

The cell id encodes the grid resolution and the (row, col) bucket so that:
  - cell_id_for(lat, lon, grid_km) is always the same for the same inputs.
  - Different grid_km values produce non-overlapping id namespaces.
  - The cell id is safe to use as a database PK (string, ≤ 40 chars).

Formula
-------
  lat_step = grid_km / 111.32           # 1° lat ≈ 111.32 km (constant)
  lon_step = grid_km / (111.32 * cos(lat_rad))   # 1° lon varies with lat

We use the latitude AT THE EQUATOR for lon quantisation (grid_km / 111.32) to
keep cell ids stable as observations cross the latitude boundary of a cell.
This is the standard MGRS-lite approach: cells are slightly non-square near the
poles but consistent.
"""

from __future__ import annotations

import math


def cell_id_for(lat: float, lon: float, grid_km: float = 5.0) -> str:
    """Return the grid cell id for a (lat, lon) point.

    Parameters
    ----------
    lat, lon:
        WGS-84 decimal degrees.
    grid_km:
        Grid resolution in kilometres (default 5 km).

    Returns
    -------
    str
        Format: ``G{grid_km}_{row}_{col}`` where row/col are signed integers
        representing the bucket indices.  Example: ``G5_2841_7109``.
    """
    if grid_km <= 0:
        raise ValueError(f"grid_km must be positive, got {grid_km}")
    step = grid_km / 111.32
    row = math.floor(lat / step)
    col = math.floor(lon / step)
    # Encode grid_km without a decimal point (5.0 → "5", 2.5 → "25")
    res_tag = f"{grid_km:g}".replace(".", "_")
    return f"G{res_tag}_{row}_{col}"
