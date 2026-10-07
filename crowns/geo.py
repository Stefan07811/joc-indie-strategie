"""The map's geography: the area it covers and how longitude and latitude become map pixels.

The map is an equirectangular projection true to scale at 42.5°N (the middle of the Balkans), so
distances are right to within ~12% from Crete to Kraków. One map pixel is KM_PER_PX kilometres.
"""

import math

LON0, LON1 = 12.0, 44.5   # Venice to beyond Trebizond
LAT0, LAT1 = 33.8, 51.6   # Crete and Cyprus to Kraków
LAT_TRUE = 42.5
KM_PER_DEG_LAT = 110.57
KM_PER_DEG_LON = 111.32 * math.cos(math.radians(LAT_TRUE))
KM_PER_PX = 1.5
WIDTH = round((LON1 - LON0) * KM_PER_DEG_LON / KM_PER_PX)
HEIGHT = round((LAT1 - LAT0) * KM_PER_DEG_LAT / KM_PER_PX)


def to_map(lon, lat):
    """(x, y) map pixels, y growing southwards."""
    return ((lon - LON0) * KM_PER_DEG_LON / KM_PER_PX, (LAT1 - lat) * KM_PER_DEG_LAT / KM_PER_PX)


def to_lonlat(x, y):
    return (LON0 + x * KM_PER_PX / KM_PER_DEG_LON, LAT1 - y * KM_PER_PX / KM_PER_DEG_LAT)
