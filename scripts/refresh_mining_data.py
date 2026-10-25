#!/usr/bin/env python3
"""Refresh public CAMI and IPIS mining records that intersect the OWR OSM boundary."""

import csv
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "OWR-Temperature-evolution public data refresh (GitHub repository)"
IPIS_URL = (
    "https://ipisresearch.be/wp-content/uploads/2026/05/"
    "cod_mines_curated_all_opendata_p_ipis.csv"
)
OSM_BOUNDARY_URL = (
    "https://nominatim.openstreetmap.org/lookup"
    "?osm_ids=R401017&format=jsonv2&polygon_geojson=1"
)
CAMI_PAGE_URL = "https://drclicences.cami.cd/EN/"
CAMI_REGISTER_URL = (
    "https://cami.cd/wp-content/uploads/2026/10/"
    "REGISTRE-DES-DROITS-MINIERS-ET-DE-CARRIERES-ACTIFS-EN-DATE-DU-30-SEPT-2026.pdf"
)
CAMI_REGISTER_SNAPSHOT = "2026-09-30"
CAMI_REGISTER_CROSSCHECK = {
    "7651": ("PE", "Actif en Force Majeure", "2020-11-10", "2045-11-09"),
    "7657": (
        "PE",
        "Actif en Déchéance pour Non Commencement",
        "2020-11-10",
        "2045-11-09",
    ),
    "8348": ("PEPM", "Actif en Force Majeure", "2020-06-16", "2025-06-15"),
    "8350": ("PEPM", "Actif en Force Majeure", "2020-06-16", "2025-06-15"),
    "14625": ("PE", "Actif en Force Majeure", "2023-03-15", "2048-03-14"),
    "14717": ("PE", "Actif en Force Majeure", "2023-02-09", "2048-02-08"),
    "14718": ("PE", "Actif en Force Majeure", "2023-02-09", "2048-02-08"),
    "14720": ("PE", "Actif en Force Majeure", "2023-02-09", "2048-02-08"),
    "15766": (
        "PR",
        "Actif en Transformation de PR en PEPM",
        "2023-12-29",
        "2028-12-28",
    ),
    "15305": (
        "Non listé",
        "Demande absente du registre des droits actifs",
        "",
        "",
    ),
}
CAMI_FEATURES = (
    (
        "CAMI published exploitation permits",
        "https://services1.arcgis.com/AYIukXzftCPbklHN/arcgis/rest/services/"
        "DRCPortal_ActiveExploitationLayer_1/FeatureServer",
        {
            0: "Large-scale Mining License",
            1: "Small-scale Mining License",
            2: "Tailings or Waste Mining License",
            3: "Permanent Quarry Mining License",
            4: "State Quarry Mining License",
        },
    ),
    (
        "CAMI published applications",
        "https://services1.arcgis.com/AYIukXzftCPbklHN/arcgis/rest/services/"
        "DRCPortal_ApplicationLayer_1/FeatureServer",
        {7: "Applications"},
    ),
)
CAMI_FIELDS = (
    "Code,Type,Status,Region,DteApplied,DteGranted,DteExpires,Parties,"
    "Commodities,GlobalID"
)
IPIS_FIELDS = (
    "pcode",
    "name",
    "visit_date",
    "source",
    "project",
    "province",
    "territoire",
    "longitude",
    "latitude",
    "mineral1",
    "mineral2",
    "mineral3",
    "location_origin",
)


def fetch(url, *, data=None, content_type=None):
    headers = {"User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def read_boundary():
    places = json.loads(fetch(OSM_BOUNDARY_URL))
    if not places or places[0].get("osm_type") != "relation":
        raise RuntimeError("OpenStreetMap did not return relation 401017.")
    geometry = places[0].get("geojson", {})
    if geometry.get("type") == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise RuntimeError(f"Unexpected OSM boundary geometry: {geometry.get('type')}.")
    return places[0], polygons


def point_on_segment(x, y, start, end):
    x1, y1 = start
    x2, y2 = end
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    if abs(cross) > 1e-10:
        return False
    return (
        min(x1, x2) - 1e-10 <= x <= max(x1, x2) + 1e-10
        and min(y1, y2) - 1e-10 <= y <= max(y1, y2) + 1e-10
    )


def point_in_ring(x, y, ring):
    inside = False
    for index, point in enumerate(ring):
        previous = ring[index - 1]
        if point_on_segment(x, y, previous, point):
            return True
        if (point[1] > y) != (previous[1] > y):
            crossing_x = (
                (previous[0] - point[0]) * (y - point[1])
                / (previous[1] - point[1])
                + point[0]
            )
            if x < crossing_x:
                inside = not inside
    return inside


def point_in_boundary(x, y, polygons):
    return any(
        point_in_ring(x, y, polygon[0])
        and not any(point_in_ring(x, y, hole) for hole in polygon[1:])
        for polygon in polygons
    )


def download_ipis(polygons):
    rows = csv.DictReader(fetch(IPIS_URL).decode("utf-8-sig").splitlines())
    matches = []
    for row in rows:
        if not row.get("longitude") or not row.get("latitude"):
            continue
        longitude, latitude = float(row["longitude"]), float(row["latitude"])
        if not point_in_boundary(longitude, latitude, polygons):
            continue
        matches.append(
            {
                "site_code": row["pcode"],
                "site_name": row["name"],
                "visit_date": row["visit_date"],
                "source": row["source"],
                "project": row["project"],
                "province": row["province"],
                "territory": row["territoire"],
                "longitude": longitude,
                "latitude": latitude,
                "minerals": ", ".join(
                    value
                    for value in (
                        row.get("mineral1", ""),
                        row.get("mineral2", ""),
                        row.get("mineral3", ""),
                    )
                    if value
                ),
                "location_origin": row["location_origin"],
                "boundary_match": "OSM relation 401017; point in polygon",
                "source_url": IPIS_URL,
            }
        )
    return sorted(matches, key=lambda row: (row["visit_date"], row["site_code"]))


def cami_portal_updated():
    html = fetch(CAMI_PAGE_URL).decode("utf-8", errors="replace")
    match = re.search(r'''MainPage\.Init\('(.+?)', "Map",''', html)
    if not match:
        raise RuntimeError("Could not read the CAMI portal's update timestamp.")
    escaped = match.group(1).replace("\\'", "'")
    config = json.loads(json.loads('"' + escaped + '"'))
    return config["DateUpdated"]


def arcgis_query(url, layer_id, geometry):
    offset = 0
    features = []
    while True:
        query = urllib.parse.urlencode(
            {
                "f": "json",
                "where": "1=1",
                "outFields": CAMI_FIELDS,
                "returnGeometry": "false",
                "geometry": json.dumps(geometry, separators=(",", ":")),
                "geometryType": "esriGeometryPolygon",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            }
        )
        response = json.loads(
            fetch(
                f"{url}/{layer_id}/query",
                data=query.encode(),
                content_type="application/x-www-form-urlencoded",
            )
        )
        if "error" in response:
            raise RuntimeError(
                f"CAMI query failed for layer {layer_id}: {response['error']}"
            )
        page = response.get("features", [])
        features.extend(page)
        offset += len(page)
        if len(page) < 1000 and not response.get("exceededTransferLimit"):
            return features
        if not page:
            return features


def date_from_milliseconds(value):
    if value is None:
        return ""
    return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).date().isoformat()


def download_cami(polygons, portal_updated, snapshot_date):
    geometry = {
        "rings": [ring for polygon in polygons for ring in polygon],
        "spatialReference": {"wkid": 4326},
    }
    records = []
    for source_name, service_url, layers in CAMI_FEATURES:
        for layer_id, layer_name in layers.items():
            features = arcgis_query(service_url, layer_id, geometry)
            for feature in features:
                attributes = feature["attributes"]
                code = str(attributes.get("Code", ""))
                register_type, register_status, register_granted, register_expires = (
                    CAMI_REGISTER_CROSSCHECK.get(
                        code,
                        ("Non vérifié", "À recouper avec le registre", "", ""),
                    )
                )
                records.append(
                    {
                        "record_category": (
                            "Application" if source_name.endswith("applications")
                            else "CAMI exploitation layer"
                        ),
                        "CAMI_code": code,
                        "permit_type": attributes.get("Type", ""),
                        "status": attributes.get("Status", ""),
                        "holder": attributes.get("Parties", ""),
                        "commodities": attributes.get("Commodities", ""),
                        "date_applied": date_from_milliseconds(
                            attributes.get("DteApplied")
                        ),
                        "date_granted": date_from_milliseconds(
                            attributes.get("DteGranted")
                        ),
                        "date_expires": date_from_milliseconds(
                            attributes.get("DteExpires")
                        ),
                        "CAMI_layer": layer_name,
                        "CAMI_layer_id": layer_id,
                        "source_layer": f"{service_url}/{layer_id}",
                        "boundary_match": "OSM relation 401017; polygon intersects",
                        "source_snapshot_date": snapshot_date,
                        "CAMI_portal_updated": portal_updated,
                        "CAMI_register_snapshot": CAMI_REGISTER_SNAPSHOT,
                        "CAMI_register_type": register_type,
                        "CAMI_register_status": register_status,
                        "CAMI_register_granted": register_granted,
                        "CAMI_register_expires": register_expires,
                        "CAMI_register_url": CAMI_REGISTER_URL,
                        "source_url": CAMI_PAGE_URL,
                        "GlobalID": attributes.get("GlobalID", ""),
                    }
                )
    return sorted(
        records,
        key=lambda row: (
            row["record_category"],
            row["CAMI_code"],
            row["CAMI_layer_id"],
        ),
    )


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    boundary, polygons = read_boundary()
    snapshot_date = dt.date.today().isoformat()
    portal_updated = cami_portal_updated()
    ipis_visits = download_ipis(polygons)
    cami_records = download_cami(polygons, portal_updated, snapshot_date)

    sites_by_code = {}
    for visit in ipis_visits:
        site = sites_by_code.setdefault(
            visit["site_code"],
            {
                "site_code": visit["site_code"],
                "site_name": visit["site_name"],
                "province": visit["province"],
                "territory": visit["territory"],
                "latitude": visit["latitude"],
                "longitude": visit["longitude"],
                "minerals": visit["minerals"],
                "first_visit_date": visit["visit_date"],
                "latest_visit_date": visit["visit_date"],
                "visit_records": 0,
                "latest_source": visit["source"],
                "latest_project": visit["project"],
                "location_origin": visit["location_origin"],
                "boundary_match": visit["boundary_match"],
                "source_url": IPIS_URL,
            },
        )
        site["visit_records"] += 1
        site["first_visit_date"] = min(site["first_visit_date"], visit["visit_date"])
        if visit["visit_date"] >= site["latest_visit_date"]:
            site.update(
                latest_visit_date=visit["visit_date"],
                latest_source=visit["source"],
                latest_project=visit["project"],
                location_origin=visit["location_origin"],
            )
    sites = sorted(sites_by_code.values(), key=lambda row: row["site_name"].casefold())

    write_csv(
        ROOT / "CAMI_Okapi_licenses.csv",
        cami_records,
        list(cami_records[0]) if cami_records else [
            "record_category", "CAMI_code", "permit_type", "status", "holder",
            "commodities", "date_applied", "date_granted", "date_expires",
            "CAMI_layer", "CAMI_layer_id", "source_layer", "boundary_match",
            "source_snapshot_date", "CAMI_portal_updated", "source_url", "GlobalID",
            "CAMI_register_snapshot", "CAMI_register_type", "CAMI_register_status",
            "CAMI_register_granted", "CAMI_register_expires", "CAMI_register_url",
        ],
    )
    write_csv(
        ROOT / "IPIS_Okapi_mine_sites.csv",
        sites,
        [
            "site_code", "site_name", "province", "territory", "latitude",
            "longitude", "minerals", "first_visit_date", "latest_visit_date",
            "visit_records", "latest_source", "latest_project", "location_origin",
            "boundary_match", "source_url",
        ],
    )
    write_csv(
        ROOT / "IPIS_Okapi_mine_visits.csv",
        ipis_visits,
        list(ipis_visits[0]) if ipis_visits else [
            "site_code", "site_name", "visit_date", "source", "project",
            "province", "territory", "longitude", "latitude", "minerals",
            "location_origin", "boundary_match", "source_url",
        ],
    )
    dashboard_data = {
        "boundary": {
            "name": boundary["display_name"],
            "osm_relation": 401017,
            "geometry_type": boundary["geojson"]["type"],
            "source_url": OSM_BOUNDARY_URL,
        },
        "snapshot_date": snapshot_date,
        "cami_portal_updated": portal_updated,
        "licenses": cami_records,
        "ipis_sites": sites,
        "ipis_visits": ipis_visits,
    }
    (ROOT / "mining-data.js").write_text(
        "const MINING_DATA = "
        + json.dumps(dashboard_data, ensure_ascii=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(cami_records)} CAMI records, {len(sites)} unique IPIS sites, "
        f"and {len(ipis_visits)} IPIS visit records. "
        f"OSM boundary relation 401017; CAMI portal updated: {portal_updated}."
    )


if __name__ == "__main__":
    main()
