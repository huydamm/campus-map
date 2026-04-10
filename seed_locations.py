import json
import math
from pathlib import Path

import pandas as pd
from shapely.geometry import shape


def parse_other_tags(other_tags):
    if not other_tags:
        return {}

    result = {}
    parts = other_tags.split('","')
    for p in parts:
        if "=>" in p:
            k, v = p.split("=>", 1)
            k = k.replace('"', '').strip()
            v = v.replace('"', '').strip()
            result[k] = v
    return result


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2

    return 2 * R * math.asin(math.sqrt(a))


def load_points(path):
    data = json.loads(Path(path).read_text())
    rows = []

    for ft in data["features"]:
        geom = ft["geometry"]
        props = ft["properties"]

        if geom["type"] != "Point":
            continue

        lon, lat = geom["coordinates"]

        tags = parse_other_tags(props.get("other_tags"))
        name = props.get("name") or tags.get("name")

        if not name:
            continue

        loc_type = tags.get("amenity") or tags.get("shop") or "unknown"

        rows.append({
            "name": name,
            "type": loc_type,
            "latitude": lat,
            "longitude": lon,
            "source": "point"
        })

    return rows


def load_polys(path):
    data = json.loads(Path(path).read_text())
    rows = []

    for ft in data["features"]:
        geom = ft["geometry"]
        props = ft["properties"]

        shp = shape(geom)
        centroid = shp.centroid

        name = props.get("name")
        if not name:
            continue

        loc_type = props.get("amenity") or props.get("shop") or "unknown"

        rows.append({
            "name": name,
            "type": loc_type,
            "latitude": centroid.y,
            "longitude": centroid.x,
            "source": "polygon"
        })

    return rows


def dedupe(rows):
    kept = []

    for r in rows:
        duplicate = False
        for k in kept:
            if r["name"].lower() == k["name"].lower():
                d = haversine_m(
                    r["latitude"], r["longitude"],
                    k["latitude"], k["longitude"]
                )
                if d < 40:
                    duplicate = True
                    break
        if not duplicate:
            kept.append(r)

    return kept


def main():
    rows = []
    rows += load_points("umass_study_pois.geojson")
    rows += load_polys("umass_study_polys.geojson")

    rows = dedupe(rows)

    df = pd.DataFrame(rows).sort_values(["type", "name"])
    df.to_csv("locations_seed.csv", index=False)

    print("Wrote locations_seed.csv with rows =", len(df))
    print(df.head(15))


if __name__ == "__main__":
    main()
