"""Open datasets on AWS and the public endpoints we read them from."""

from __future__ import annotations

from typing import Any

OVERTURE_BUCKET = "overturemaps-us-west-2"
OVERTURE_RELEASE = "2026-09-23.1"
OVERTURE_BUILDINGS = (
    f"s3://{OVERTURE_BUCKET}/release/{OVERTURE_RELEASE}/theme=buildings/type=building/*.parquet"
)

# Meta / WRI canopy height v2 (DINOv3), web-mercator zoom-10 tiles at ~1.2 m, uint8 metres
CANOPY_VERSION = "dinov3_global_chm_v2_ml3"
CANOPY_TILE = (
    "https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/"
    f"{CANOPY_VERSION}/chm/{{quadkey}}.tif"
)
CANOPY_ZOOM = 10

DEM_TILE = "https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif"

OVERPASS = "https://overpass-api.de/api/interpreter"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

USER_AGENT = "neem/0.1 (+https://github.com/riteshroshann/neem)"

# GDAL settings for reading cloud-optimised GeoTIFFs over HTTP with range requests
GDAL_HTTP_ENV: dict[str, Any] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
    "GDAL_CACHEMAX": 512,
}
