#!/usr/bin/env python3
"""Refresh public CAMI and IPIS mining records that intersect the OWR OSM boundary."""

import csv
import datetime as dt
import json
import math
import re
import urllib.parse
import urllib.request
import unicodedata
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "OWR-Temperature-evolution public data refresh (GitHub repository)"
IPIS_URL = (
    "https://ipisresearch.be/wp-content/uploads/2026/05/"
    "cod_mines_curated_all_opendata_p_ipis.csv"
)
HANSEN_RASTER_BASE = (
    "https://storage.googleapis.com/earthenginepartners-hansen/"
    "GFC-2024-v1.12/"
)
HANSEN_VERSION = "UMD/Hansen Global Forest Change v1.12 (2001–2024)"
HANSEN_URL = (
    "https://developers.google.com/earth-engine/datasets/catalog/"
    "UMD_hansen_global_forest_change_2024_v1_12"
)
HANSEN_TILE = "10N_020E"
MINE_BUFFER_METERS = 500
MINING_DATA_WAREHOUSE_URL = "https://www.miningdatawarehouse.cd"
MINING_DATA_WAREHOUSE_SEARCH = (
    f"{MINING_DATA_WAREHOUSE_URL}/home/operateur/search/all"
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


def pixel_area_hectares(latitude):
    semi_major_axis = 6378137
    eccentricity_squared = 0.00669437999014
    latitude_radians = math.radians(latitude)
    denominator = 1 - eccentricity_squared * math.sin(latitude_radians) ** 2
    prime_vertical_radius = semi_major_axis / math.sqrt(denominator)
    meridional_radius = (
        semi_major_axis
        * (1 - eccentricity_squared)
        / denominator**1.5
    )
    pixel_width = (
        prime_vertical_radius
        * math.cos(latitude_radians)
        * 0.00025
        * math.pi
        / 180
    )
    pixel_height = (
        meridional_radius
        * 0.00025
        * math.pi
        / 180
    )
    return pixel_width * pixel_height / 10000


def download_mining_proximity(sites, polygons):
    try:
        import numpy as np
        import rasterio
        from rasterio.windows import Window
    except ImportError as error:
        raise RuntimeError(
            "Hansen proximity calculation requires rasterio; run "
            "'python3 -m pip install -r requirements-mining.txt'."
        ) from error

    base = HANSEN_RASTER_BASE
    loss_url = (
        f"/vsicurl/{base}Hansen_GFC-2024-v1.12_lossyear_{HANSEN_TILE}.tif"
    )
    canopy_url = (
        f"/vsicurl/{base}Hansen_GFC-2024-v1.12_treecover2000_{HANSEN_TILE}.tif"
    )
    pixels = {}
    with rasterio.open(loss_url) as loss_dataset, rasterio.open(
        canopy_url
    ) as canopy_dataset:
        if (
            loss_dataset.bounds != canopy_dataset.bounds
            or loss_dataset.transform != canopy_dataset.transform
            or loss_dataset.bounds.left != 20
            or loss_dataset.bounds.bottom != 0
        ):
            raise RuntimeError("Unexpected Hansen raster tile or grid.")

        for site in sites:
            longitude = site["longitude"]
            latitude = site["latitude"]
            if not (20 <= longitude < 30 and 0 <= latitude < 10):
                raise RuntimeError(
                    f"IPIS site {site['site_code']} lies outside Hansen tile "
                    f"{HANSEN_TILE}; the proximity tile needs updating."
                )
            lat_radius = MINE_BUFFER_METERS / 110000
            lon_radius = lat_radius / math.cos(math.radians(latitude))
            raw_window = loss_dataset.window(
                longitude - lon_radius,
                latitude - lat_radius,
                longitude + lon_radius,
                latitude + lat_radius,
            )
            col_start = max(0, math.floor(raw_window.col_off))
            row_start = max(0, math.floor(raw_window.row_off))
            col_stop = min(
                loss_dataset.width,
                math.ceil(raw_window.col_off + raw_window.width),
            )
            row_stop = min(
                loss_dataset.height,
                math.ceil(raw_window.row_off + raw_window.height),
            )
            window = Window(
                col_start,
                row_start,
                col_stop - col_start,
                row_stop - row_start,
            )
            loss = loss_dataset.read(1, window=window)
            canopy = canopy_dataset.read(1, window=window)
            transform = loss_dataset.window_transform(window)
            columns = transform.c + (
                np.arange(loss.shape[1]) + 0.5
            ) * transform.a
            latitudes = transform.f + (
                np.arange(loss.shape[0]) + 0.5
            ) * transform.e
            longitude_grid, latitude_grid = np.meshgrid(columns, latitudes)
            site_latitude_radians = math.radians(latitude)
            delta_latitude = np.radians(latitude_grid - latitude)
            delta_longitude = np.radians(longitude_grid - longitude)
            haversine = (
                np.sin(delta_latitude / 2) ** 2
                + math.cos(site_latitude_radians)
                * np.cos(np.radians(latitude_grid))
                * np.sin(delta_longitude / 2) ** 2
            )
            distance = 2 * 6371008.8 * np.arcsin(
                np.sqrt(np.clip(haversine, 0, 1))
            )
            candidate_rows, candidate_columns = np.where(
                (distance <= MINE_BUFFER_METERS)
                & (loss >= 1)
                & (loss <= 24)
                & (canopy >= 30)
            )
            for row_index, column_index in zip(
                candidate_rows, candidate_columns
            ):
                pixel_row = row_start + int(row_index)
                pixel_column = col_start + int(column_index)
                pixel_longitude = longitude_grid[row_index, column_index]
                pixel_latitude = latitude_grid[row_index, column_index]
                in_reserve_proxy = point_in_boundary(
                    pixel_longitude, pixel_latitude, polygons
                )
                zone = "Reserve" if in_reserve_proxy else "Buffer_0_10km"
                pixels[(pixel_row, pixel_column)] = (
                    int(loss[row_index, column_index]),
                    zone,
                    pixel_area_hectares(pixel_latitude),
                )

    totals = {
        (year, zone): {"hansen_loss_pixels": 0, "hansen_loss_ha": 0.0}
        for year in range(2001, 2025)
        for zone in ("Reserve", "Buffer_0_10km")
    }
    for loss_year, zone, area_hectares in pixels.values():
        record = totals[(2000 + loss_year, zone)]
        record["hansen_loss_pixels"] += 1
        record["hansen_loss_ha"] += area_hectares
    records = [
        {
            "year": year,
            "zone": zone,
            **totals[(year, zone)],
            "site_count": len(sites),
            "buffer_meters": MINE_BUFFER_METERS,
            "activity_years_known": False,
            "method": HANSEN_VERSION,
            "source_url": HANSEN_URL,
            "site_source_url": IPIS_URL,
            "boundary_source_url": (
                "https://www.openstreetmap.org/relation/401017"
            ),
        }
        for year in range(2001, 2025)
        for zone in ("Reserve", "Buffer_0_10km")
    ]
    return records


class HtmlTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.cell_text = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "tr":
            self.current_row = {"cells": [], "links": []}
        elif tag in ("td", "th") and self.current_row is not None:
            self.current_cell = []
            self.cell_text = []
        elif tag == "a" and self.current_row is not None:
            href = attributes.get("href")
            if href:
                self.current_row["links"].append(href)

    def handle_data(self, data):
        if self.current_cell is not None:
            self.cell_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.current_row is not None:
            self.current_row["cells"].append(
                " ".join(" ".join(self.cell_text).split())
            )
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None


def normalize_operator_name(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"\s*\([^)]*%\)\s*", " ", value)
    value = re.sub(r"[^A-Za-z0-9]+", " ", value).upper()
    legal_suffixes = {"SARL", "SPRL", "SAS", "SA", "LTD", "LIMITED"}
    tokens = value.split()
    while tokens and tokens[-1] in legal_suffixes:
        tokens.pop()
    return " ".join(tokens)


def parse_html_tables(html):
    parser = HtmlTableParser()
    parser.feed(html)
    return parser.rows


def fetch_warehouse_operator(holder):
    search_term = normalize_operator_name(holder)
    request = urllib.request.Request(
        MINING_DATA_WAREHOUSE_SEARCH,
        data=urllib.parse.urlencode({"data": search_term}).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{MINING_DATA_WAREHOUSE_URL}/operateur/all",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        html = response.read().decode("utf-8", errors="replace")
    rows = parse_html_tables(html)
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if "Nom / Raison sociale" in row["cells"]
        ),
        None,
    )
    if header_index is None:
        raise RuntimeError(
            f"Could not parse Mining Data Warehouse search for {holder!r}."
        )
    headers = rows[header_index]["cells"]
    matches = []
    for row in rows[header_index + 1 :]:
        if not row["cells"] or row["cells"][0] == "Aucun opérateur trouvé pour cette recherche.":
            continue
        operator = dict(zip(headers, row["cells"]))
        if normalize_operator_name(operator.get("Nom / Raison sociale", "")) != normalize_operator_name(holder):
            continue
        profile_path = next(
            (
                href
                for href in row["links"]
                if re.fullmatch(r"/operateur/\d+/all", href)
            ),
            "",
        )
        if not profile_path:
            raise RuntimeError(
                f"Warehouse match for {holder!r} has no operator profile link."
            )
        profile_url = urllib.parse.urljoin(
            f"{MINING_DATA_WAREHOUSE_URL}/", profile_path
        )
        profile_html = fetch(profile_url).decode("utf-8", errors="replace")
        profile = {}
        for detail_row in parse_html_tables(profile_html):
            cells = detail_row["cells"]
            if len(cells) >= 2:
                profile[cells[0]] = cells[1]
        matches.append(
            {
                "operator_name": operator.get("Nom / Raison sociale", ""),
                "warehouse_id": profile_path.split("/")[2],
                "warehouse_status": profile.get("Statut", operator.get("Statut", "")),
                "warehouse_province": profile.get("Province", operator.get("Province", "")),
                "warehouse_category": profile.get("Catégorie", operator.get("Catégorie", "")),
                "warehouse_sector": profile.get("Secteur", operator.get("Secteur", "")),
                "warehouse_created": profile.get("Date de création", ""),
                "warehouse_url": profile_url,
            }
        )
    return matches


def download_warehouse_operators(cami_records, snapshot_date):
    holder_groups = {}
    for record in cami_records:
        key = normalize_operator_name(record["holder"])
        holder_groups.setdefault(key, []).append(record)
    records = []
    for holder_group in holder_groups.values():
        holder = holder_group[0]["holder"]
        matches = fetch_warehouse_operator(holder)
        if len(matches) == 1:
            match_status = "Correspondance exacte du nom"
            operator = matches[0]
        elif len(matches) > 1:
            match_status = "Correspondances multiples — à vérifier"
            operator = {
                "operator_name": " | ".join(
                    match["operator_name"] for match in matches
                ),
                "warehouse_id": "",
                "warehouse_status": "",
                "warehouse_province": "",
                "warehouse_category": "",
                "warehouse_sector": "",
                "warehouse_created": "",
                "warehouse_url": MINING_DATA_WAREHOUSE_URL + "/operateur/all",
            }
        else:
            match_status = "Aucune correspondance exacte retournée"
            operator = {
                "operator_name": "",
                "warehouse_id": "",
                "warehouse_status": "",
                "warehouse_province": "",
                "warehouse_category": "",
                "warehouse_sector": "",
                "warehouse_created": "",
                "warehouse_url": MINING_DATA_WAREHOUSE_URL + "/operateur/all",
            }
        records.append(
            {
                "CAMI_holder": re.sub(
                    r"\s*\([^)]*%\)\s*", "", holder
                ).strip(),
                "CAMI_codes": ", ".join(
                    sorted(
                        record["CAMI_code"]
                        for record in holder_group
                    )
                ),
                "warehouse_match": match_status,
                **operator,
                "warehouse_snapshot_date": snapshot_date,
                "match_method": (
                    "Recherche du nom dans le registre MDW; égalité après "
                    "normalisation des accents, ponctuations et formes juridiques"
                ),
                "source_url": MINING_DATA_WAREHOUSE_URL + "/operateur/all",
            }
        )
    return records


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
    warehouse_operators = download_warehouse_operators(
        cami_records, snapshot_date
    )

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
    proximity = download_mining_proximity(sites, polygons)

    write_csv(
        ROOT / "cami_rights.csv",
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
        ROOT / "ipis_sites.csv",
        sites,
        [
            "site_code", "site_name", "province", "territory", "latitude",
            "longitude", "minerals", "first_visit_date", "latest_visit_date",
            "visit_records", "latest_source", "latest_project", "location_origin",
            "boundary_match", "source_url",
        ],
    )
    write_csv(
        ROOT / "ipis_visits.csv",
        ipis_visits,
        list(ipis_visits[0]) if ipis_visits else [
            "site_code", "site_name", "visit_date", "source", "project",
            "province", "territory", "longitude", "latitude", "minerals",
            "location_origin", "boundary_match", "source_url",
        ],
    )
    write_csv(
        ROOT / "hansen_near_mines.csv",
        proximity,
        [
            "year", "zone", "hansen_loss_pixels", "hansen_loss_ha",
            "site_count", "buffer_meters", "activity_years_known", "method",
            "source_url", "site_source_url", "boundary_source_url",
        ],
    )
    write_csv(
        ROOT / "mining_operators.csv",
        warehouse_operators,
        list(warehouse_operators[0]) if warehouse_operators else [
            "CAMI_holder", "CAMI_codes", "warehouse_match", "operator_name",
            "warehouse_id", "warehouse_status", "warehouse_province",
            "warehouse_category", "warehouse_sector", "warehouse_created",
            "warehouse_url", "warehouse_snapshot_date", "match_method",
            "source_url",
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
        "proximity": proximity,
        "warehouse_operators": warehouse_operators,
    }
    (ROOT / "mining_data.js").write_text(
        "const MINING_DATA = "
        + json.dumps(dashboard_data, ensure_ascii=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(cami_records)} CAMI records, {len(sites)} unique IPIS sites, "
        f"{len(ipis_visits)} IPIS visit records, {len(proximity)} "
        "Hansen proximity rows, and "
        f"{sum(record['warehouse_match'] == 'Correspondance exacte du nom' for record in warehouse_operators)} "
        "exact Mining Data Warehouse operator matches. "
        f"OSM boundary relation 401017; CAMI portal updated: {portal_updated}."
    )


if __name__ == "__main__":
    main()
