#!/usr/bin/env python
# OPERA DISP: extract internal water_mask variable, subset by bbox/idx, write as COG.

import os
import json
import argparse
from typing import Any, Optional, Tuple
import xml.etree.ElementTree as ET

import requests
import numpy as np
import xarray as xr
import rioxarray  # registers .rio
import pyproj
from shapely.geometry import box
from shapely.ops import transform as shp_transform

from maap.maap import MAAP
from s3fs import S3FileSystem


# ----------------- CLI -----------------
def parse_args():
    p = argparse.ArgumentParser(
        description="OPERA DISP: export water_mask -> COG (uint8), with optional bbox/idx subsetting."
    )
    p.add_argument("--short-name", default="OPERA_L3_DISP-S1_V1", help="CMR short name")
    p.add_argument("--temporal", default=None,
                   help="Temporal range 'YYYY-MM-DDTHH:MM:SSZ,YYYY-MM-DDTHH:MM:SSZ'")
    p.add_argument("--bbox", default=None,
                   help="WGS84 bbox 'minx,miny,maxx,maxy'")
    p.add_argument("--limit", type=int, default=10, help="Max granules to search")
    p.add_argument("--granule-ur", default=None, help="Optional fixed GranuleUR")
    p.add_argument("--tile", type=int, default=256, help="COG tile size")
    p.add_argument("--compress", default="DEFLATE", help="COG compression")
    p.add_argument("--overview-resampling", default="nearest",
                   help="COG overview resampling (nearest for masks)")
    p.add_argument("--out-name", default="water_mask_subset.cog.tif", help="Output filename")
    p.add_argument("--dest", default=None,
                   help="Relative output directory (e.g., 'output') — s1-example style.")
    p.add_argument("--idx-window", default=None, help="Index window 'y0:y1,x0:x1'")
    p.add_argument("--s3-url", default=None,
                   help="Direct s3:// path to a .nc granule (bypass CMR search)")
    args, _ = p.parse_known_args()

    # normalize accidental whitespace from UI
    if args.temporal:
        args.temporal = args.temporal.strip()
    if args.bbox:
        args.bbox = args.bbox.strip()
    if args.granule_ur:
        args.granule_ur = args.granule_ur.strip()
    if args.s3_url:
        args.s3_url = args.s3_url.strip()
    if args.dest:
        args.dest = args.dest.strip()

    return args


# ----------------- Helpers -----------------
def parse_bbox(bbox_str: str) -> Tuple[float, float, float, float]:
    vals = [float(v) for v in bbox_str.split(",")]
    if len(vals) != 4:
        raise ValueError("bbox must be 'minx,miny,maxx,maxy'")
    minx, miny, maxx, maxy = vals
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox min values must be < max values")
    return minx, miny, maxx, maxy


def ensure_wgs84_bbox_to_target(bbox, target_crs: Any):
    if not target_crs:
        return bbox
    t = pyproj.Transformer.from_crs("EPSG:4326", target_crs, always_xy=True).transform
    minx, miny, maxx, maxy = bbox
    return shp_transform(t, box(minx, miny, maxx, maxy)).bounds


def _extract_s3_url_from_result(r) -> Optional[str]:
    # Try MAAP/CMR dict structure
    if isinstance(r, dict):
        try:
            urls = r["Granule"]["OnlineAccessURLs"]["OnlineAccessURL"]
            if isinstance(urls, list):
                for u in urls:
                    ustr = u.get("URL") if isinstance(u, dict) else u
                    if isinstance(ustr, str) and ustr.startswith("s3://"):
                        return ustr
            elif isinstance(urls, dict):
                u0 = urls.get("URL")
                if isinstance(u0, str) and u0.startswith("s3://"):
                    return u0
        except Exception:
            pass
    # Some SDK objects expose getDownloadUrl()
    if hasattr(r, "getDownloadUrl"):
        try:
            url = r.getDownloadUrl()
            if isinstance(url, str) and url.startswith("s3://"):
                return url
        except Exception:
            pass
    return None


def _first_s3_from_umm(umm_item) -> Optional[str]:
    # UMM JSON -> look in RelatedUrls first
    try:
        for u in umm_item["umm"].get("RelatedUrls", []):
            url = u.get("URL")
            if isinstance(url, str) and url.startswith("s3://"):
                return url
    except Exception:
        pass
    # Fallbacks
    try:
        lst = umm_item["umm"]["OnlineAccessURLs"]["OnlineAccessURL"]
        if isinstance(lst, list):
            for it in lst:
                u = it.get("URL") if isinstance(it, dict) else it
                if isinstance(u, str) and u.startswith("s3://"):
                    return u
        elif isinstance(lst, dict):
            u = lst.get("URL")
            if isinstance(u, str) and u.startswith("s3://"):
                return u
    except Exception:
        pass
    return None


def pick_granule_url(maap: MAAP, short_name, temporal, bbox, limit, fixed_ur=None):
    # Find collection concept-id
    coll = maap.searchCollection(cmr_host="cmr.earthdata.nasa.gov", short_name=short_name)
    if not coll:
        raise RuntimeError(f"No collection found for {short_name}")
    concept_id = coll[0].get("concept-id")

    # Build SDK query (granule search expects 'collection_concept_id')
    q = {"cmr_host": "cmr.earthdata.nasa.gov", "collection_concept_id": concept_id}
    if temporal:
        q["temporal"] = temporal
    if bbox:
        q["bounding_box"] = bbox

    # First try the SDK (XML), catch parser hiccups and fall back to UMM-JSON
    try:
        results = maap.searchGranule(limit=limit, **q)
    except ET.ParseError as e:
        # Fallback to CMR UMM-JSON (no XML parsing)
        params = {
            "collection_concept_id": concept_id,
            "page_size": str(limit or 10),
        }
        if temporal:
            params["temporal"] = temporal
        if bbox:
            params["bounding_box"] = bbox
        if fixed_ur:
            params["granule_ur"] = fixed_ur

        r = requests.get(
            "https://cmr.earthdata.nasa.gov/search/granules.umm_json",
            params=params,
            timeout=60,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"CMR UMM-JSON request failed: status={r.status_code} url={r.url}"
            ) from e
        data = r.json()
        items = data.get("items", [])
        if not items:
            raise RuntimeError("No granules found (UMM-JSON fallback).")
        if fixed_ur:
            items = [it for it in items if it.get("umm", {}).get("GranuleUR") == fixed_ur]
            if not items:
                raise RuntimeError(f"GranuleUR '{fixed_ur}' not found in UMM-JSON results.")
        s3_url = _first_s3_from_umm(items[0])
        if not s3_url:
            raise RuntimeError("Could not find s3:// URL in UMM-JSON item.")
        creds = maap.aws.earthdata_s3_credentials("https://cumulus.asf.alaska.edu/s3credentials")
        return s3_url, {"granule": items[0], "aws_creds": creds}

    if not results:
        raise RuntimeError("No granules found.")

    # Respect fixed UR if provided
    def _gur(r):
        return r.get("Granule", {}).get("GranuleUR") if isinstance(r, dict) else getattr(r, "GranuleUR", None)

    if fixed_ur:
        pick = next((r for r in results if _gur(r) == fixed_ur), None)
        if pick is None:
            raise RuntimeError(f"GranuleUR '{fixed_ur}' not found in SDK results.")
    else:
        pick = results[0]

    s3_url = _extract_s3_url_from_result(pick)
    if not (isinstance(s3_url, str) and s3_url.startswith("s3://")) and hasattr(pick, "getDownloadUrl"):
        try:
            s3_try = pick.getDownloadUrl()
            if isinstance(s3_try, str) and s3_try.startswith("s3://"):
                s3_url = s3_try
        except Exception:
            pass

    if not (isinstance(s3_url, str) and s3_url.startswith("s3://")):
        # As a last resort, dump the first 1k of a raw XML response for debugging
        params = {
            "collection_concept_id": concept_id,
            "page_size": str(limit or 10),
        }
        if temporal:
            params["temporal"] = temporal
        if bbox:
            params["bounding_box"] = bbox
        rr = requests.get("https://cmr.earthdata.nasa.gov/search/granules.xml",
                          params=params, timeout=60)
        raise RuntimeError(
            "Could not resolve s3:// URL from granule metadata.\n"
            f"SDK results example (xml head {len(rr.text[:1000])} chars):\n{rr.text[:1000]}"
        )

    creds = maap.aws.earthdata_s3_credentials("https://cumulus.asf.alaska.edu/s3credentials")
    print("mlucas s3_url: ", s3_url)
    return s3_url, {"granule": pick, "aws_creds": creds}


def open_remote_dataset(granule_url: str, aws_creds: dict) -> xr.Dataset:
    """
    Open a remote OPERA DISP NetCDF via S3 with lazy loading.
    Tries multiple xarray engines and applies sensible I/O params.
    """
    os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

    s3 = S3FileSystem(
        key=aws_creds["accessKeyId"],
        secret=aws_creds["secretAccessKey"],
        token=aws_creds["sessionToken"],
        client_kwargs={"region_name": "us-west-2"},
    )

    print("mlucas aws key: ", aws_creds["accessKeyId"])
    print("mlucas granule: ", granule_url)

    # Sanity check (raises if key not found)
    _ = s3.info(granule_url)

    # Common I/O parameters to avoid unnecessary caching and to respect CF
    io_params = dict(
        decode_cf=True,
        mask_and_scale=True,
        cache=False,
    )

    # Try engines in order; return on first success
    for engine in ["h5netcdf", "netcdf4", "scipy"]:
        try:
            fobj = s3.open(granule_url, "rb")
            ds = xr.open_dataset(
                fobj,
                engine=engine,
                chunks="auto",   # lazy, dask-backed reads
                **io_params,
            )
            # Touch metadata to confirm open
            _ = list(ds.sizes.items())[:1]
            return ds
        except Exception:
            continue

    raise RuntimeError(f"Failed to open {granule_url} (tried h5netcdf/netcdf4/scipy)")


def get_water_mask(ds: xr.Dataset) -> xr.DataArray:
    if "water_mask" not in ds:
        raise RuntimeError("Dataset has no 'water_mask' variable.")
    da = ds["water_mask"]
    if "time" in da.dims and da.sizes.get("time", 1) > 1:
        da = da.isel(time=0)
    if "band" in da.dims and da.sizes.get("band", 1) == 1:
        da = da.isel(band=0, drop=True)
    return (da > 0)  # boolean mask


def subset_bbox(da: xr.DataArray, bbox) -> xr.DataArray:
    if da.rio.crs is None:
        da = da.rio.write_crs("EPSG:4326")
    dst_bbox = ensure_wgs84_bbox_to_target(bbox, da.rio.crs)
    return da.rio.clip_box(*dst_bbox)


def subset_idx(da: xr.DataArray, idx_spec: str) -> xr.DataArray:
    yspec, xspec = idx_spec.split(",")
    y0, y1 = [int(x) if x else None for x in yspec.split(":")]
    x0, x1 = [int(x) if x else None for x in xspec.split(":")]
    return da.isel(y=slice(y0, y1), x=slice(x0, x1))


def write_cog(da: xr.DataArray, out_path: str,
              nodata_val=255, tile=256,
              compress="DEFLATE", overview_resampling="nearest"):
    da = da.astype("uint8").rio.write_nodata(nodata_val, inplace=False)
    da.rio.to_raster(out_path,
                     driver="COG",
                     dtype="uint8",
                     nodata=nodata_val,
                     blockxsize=tile,
                     blockysize=tile,
                     compress=compress,
                     overview_resampling=overview_resampling,
                     BIGTIFF="IF_NEEDED")
    return out_path


# ----------------- Main -----------------
def main():
    args = parse_args()

    # Log inputs (goes to _stdout.txt)
    print(json.dumps({
        "args": {
            "short_name": args.short_name,
            "temporal": args.temporal,
            "bbox": args.bbox,
            "limit": args.limit,
            "granule_ur": args.granule_ur,
            "s3_url": args.s3_url
        }
    }))

    # s1-style: prefer --dest, then USER_OUTPUT_DIR, then 'output'
    out_dir = args.dest or os.environ.get("USER_OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, args.out_name)

    maap = MAAP()

    # Choose source: direct s3 or CMR discovery
    if args.s3_url:
        url = args.s3_url
        meta = {
            "granule": None,
            "aws_creds": maap.aws.earthdata_s3_credentials(
                "https://cumulus.asf.alaska.edu/s3credentials"
            ),
        }
    else:
        url, meta = pick_granule_url(
            maap,
            args.short_name,
            args.temporal,
            args.bbox,
            args.limit,
            args.granule_ur,
        )

    ds = open_remote_dataset(url, meta["aws_creds"])

    try:
        # Build mask and optionally subset
        wm = get_water_mask(ds)
        if args.idx_window:
            wm = subset_idx(wm, args.idx_window)
        elif args.bbox:
            wm = subset_bbox(wm, parse_bbox(args.bbox))

        # Write COG and report
        out = write_cog(
            wm,
            out_path,
            tile=args.tile,
            compress=args.compress,
            overview_resampling=args.overview_resampling,
        )

        print(f"Saved COG to {out}")

        if os.path.exists(out):
            print(json.dumps({
                "status": "OK",
                "outfile": out,
                "size_mb": round(os.path.getsize(out) / 1e6, 2),
            }))
        else:
            raise SystemExit(1)
    finally:
        # Release S3/file handles explicitly
        try:
            ds.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
