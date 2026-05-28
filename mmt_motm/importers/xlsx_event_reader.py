import json
import os
import re
from glob import glob
from datetime import datetime
import time
from openpyxl import load_workbook, Workbook
from mmt_motm.importers.coordinates_utils import (
    search_nominatim,
    extract_wikidata_coordinates,
    extract_geonames_coordinates,
    extract_urls,
)

# ==================================================
# Utility functions
# ==================================================

def clean_value(value):
    if not value:
        return None

    value = str(value).strip()

    if value in ["", "-", "–", "—"]:
        return None

    return value


def parse_date(value):
    if not value:
        return None

    value = str(value).strip()

    # formato tedesco: 15.6.1921
    try:
        return datetime.strptime(value, "%d.%m.%Y").date().isoformat()
    except Exception:
        pass

    # formato slash: 15/06/1921
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except Exception:
        pass

    return None

def split_place_name(name):
    if not name:
        return {"city": None, "address": None, "region": None}

    parts = [p.strip() for p in name.split(",") if p.strip()]

    if len(parts) == 1:
        return {"city": parts[0], "address": None, "region": None}

    return {
        "city": parts[-1],         
        "address": ", ".join(parts[:-1]),
        "region": None
    }

def is_specific_place(name):
    """
    Decide if place_name is likely an address or specific location
    """
    if not name:
        return False

    # presenza di numero → indirizzo
    if any(char.isdigit() for char in name):
        return True

    # più parti separate → luogo più specifico
    parts = [p.strip() for p in name.split(",")]
    if len(parts) > 1:
        return True

    return False

def is_same_place(a, b):

    if not a["lat"] or not b["lat"]:
        return False

    lat_diff = abs(float(a["lat"]) - float(b["lat"]))
    lon_diff = abs(float(a["lon"]) - float(b["lon"]))

    if lat_diff < 0.00001 and lon_diff < 0.00001:
        return True

    name_a = a["name"].strip().lower()
    name_b = b["name"].strip().lower()

    if name_a == name_b:
        if lat_diff < 0.01 and lon_diff < 0.01:
            return True

    return False

# =============================
# Location (lat,long) from data
# =============================
def resolve_location(place_name, wikidata_id=None, geonames_id=None,
                     wikidata_cache=None, geonames_cache=None):
    """
    Resolve location using:
    - Nominatim ONLY for specific places (addresses)
    - Wikidata or GeoNames
    """
    parsed = split_place_name(place_name)

    coords = None
    source = None
    resolved_name = None

    # ============================
    # 1. NOMINATIM 
    # ============================
    if is_specific_place(place_name) or (not wikidata_id and not geonames_id):
        query = place_name
        if parsed["address"] and parsed["city"]:
            query = f"{parsed['address']}, {parsed['city']}"

        result = search_nominatim(query)

        if result:
            coords = {
                "lat": float(result["lat"]),
                "lon": float(result["lon"])
            }
            source = "nominatim"
            resolved_name = result.get("display_name")


    # ============================
    # 2. WIKIDATA
    # ============================
    if not coords and wikidata_id:
        cache_key = wikidata_id
        if wikidata_id.startswith("Q"):
            api_id = f"https://www.wikidata.org/wiki/{wikidata_id}"
        else:
            api_id = wikidata_id
        if wikidata_cache is not None and cache_key in wikidata_cache:
            result = wikidata_cache[cache_key]
        else:
            try:
                time.sleep(0.25)
                result = extract_wikidata_coordinates(api_id)
            except Exception as e:
                result = None

            if wikidata_cache is not None:
                wikidata_cache[cache_key] = result

        if result and result.get("lat") and result.get("long"):
            coords = {
                "lat": float(result["lat"]),
                "lon": float(result["long"])
            }
            source = "wikidata"
            resolved_name = result.get("label")

    # ============================
    # 3. GEONAMES
    # ============================  
    if not coords and geonames_id:

        if geonames_id.isdigit():
            geonames_id = f"https://www.geonames.org/{geonames_id}/"

        cache_key = geonames_id

        if geonames_cache is not None and cache_key in geonames_cache:
            result = geonames_cache[cache_key]
        else:
            try:
                result = extract_geonames_coordinates(geonames_id)
            except Exception as e:
                result = None

            if geonames_cache is not None:
                geonames_cache[cache_key] = result

        if result and result.get("lat") and result.get("long"):
            coords = {
                "lat": float(result["lat"]),
                "lon": float(result["long"])
            }
            source = "geonames"
            resolved_name = ", ".join(filter(None, [
                result.get("name"),
                result.get("adminName1"),
                result.get("countryName")
            ]))

    # ============================
    # 4. REGION fallback 
    # ============================
    if not coords and parsed["region"]:
        result = search_nominatim(parsed["region"])
        if result:
            coords = {
                "lat": float(result["lat"]),
                "lon": float(result["lon"])
            }
            source = "nominatim"
            resolved_name = result.get("display_name")

    return {
        "original_name": place_name,
        "city": parsed["city"],
        "address": parsed["address"],
        "region": parsed["region"],
        "lat": coords["lat"] if coords else None,
        "lon": (
            coords.get("lon") or coords.get("long") or coords.get("lng")
        ) if coords else None,
        "source": source,
        "resolved": coords is not None,
        "resolved_name": resolved_name,
    }

# ==================================================
# SINGLE FILE READER
# ==================================================
def read_event_sheet(xlsx_path, sheet_name=None, write_json=False):

    wb = load_workbook(xlsx_path)
    sheet = wb[sheet_name] if sheet_name else wb.active

    rows = list(sheet.iter_rows(values_only=True))

    # ============================
    # PERSON INFO (FIRST ROW)
    # ============================
    first_row = rows[0]

    person_name = None
    person_id = None

    for cell in first_row:
        if cell:
            person_name = str(cell).strip()
            break

    # person_id
    for cell in first_row:
        if cell and "person_id" in str(cell):
            text = str(cell)
            match = re.search(r"person_id:\s*([A-Za-z0-9_]+)", text)
            if match:
                person_id = match.group(1)

    # ============================
    # HEADER (ROW 3)
    # ============================
    header = []
    for cell in rows[2]:
        if cell:
            header.append(str(cell).strip())
        else:
            header.append("")

    # ============================
    # DATA STRUCTURES
    # ============================
    events = []
    event_types = set()
    locations = {}
    wikidata_cache = {}
    geonames_cache = {}

    # ============================
    # DATA ROWS
    # ============================
    for row in rows[3:]:

        if not row or all(cell is None for cell in row):
            continue

        data = dict(zip(header, row))

        # ------------------------
        # EVENT
        # ------------------------
        raw_date = clean_value(data.get("date_label"))
        event = {
            "event_label": clean_value(data.get("event_label")),
            "event_type": clean_value(data.get("event_type")),
            "place_type": clean_value(data.get("place_type")),
            "place_category": clean_value(data.get("place_category")),
            "date": parse_date(raw_date),
            "date_original": raw_date,
            "date_certainty": clean_value(data.get("date_certainty")),
            "notes": clean_value(data.get("notes")),
        }

        # ------------------------
        # EVENT TYPE
        # ------------------------
        if event["event_type"]:
            event_types.add(event["event_type"])

        # ------------------------
        # EXTERNAL LINKS
        # ------------------------
        wikidata_field = clean_value(data.get("wikidata_qid"))
        geonames_field = clean_value(data.get("geonames_id"))

        wikidata_id = wikidata_field
        geonames_id = geonames_field

        wiki_url = None
        geo_url = None
        links = []

        links_raw = clean_value(data.get("external_links"))

        if links_raw:
            pairs = extract_urls(links_raw)

            for text, url_map in pairs:
                for domain, url in url_map.items():
                    split_urls = url.split(" | ")
                    for u in split_urls:
                        u = u.strip()
                        if not u:
                            continue
 
                        if "wikidata.org" in u:
                            if not wikidata_field or not wikidata_field.strip():
                                wiki_url = u
                            links.append(u)

                        elif "geonames.org" in u:
                            if not geonames_field or not geonames_field.strip():
                                geo_url = u
                            links.append(u)

                        else:
                            links.append(u)

        
        wikidata_id = wikidata_field or wiki_url
        geonames_id = geonames_field or geo_url

        if links:
            event["external_links"] = list(dict.fromkeys(links))

        # ------------------------
        # LOCATION
        # ------------------------
        location_name = clean_value(data.get("place_name"))

        location = resolve_location(
            location_name,
            wikidata_id=wikidata_id,
            geonames_id=geonames_id,
            wikidata_cache=wikidata_cache,
            geonames_cache=geonames_cache
        )

        event["location"] = location

        # ------------------------
        # LOCATION ID + REGISTRY
        # ------------------------

        def normalize(name):
            return name.strip().lower() if name else ""

        if location.get("source") == "wikidata" and wikidata_id:
            key = f"wd_{wikidata_id}"
        elif location.get("source") == "geonames" and geonames_id:
            geo_id = geonames_id.split("/")[-2] if "/" in geonames_id else geonames_id
            key = f"geo_{geo_id}"
        else:
            key = f"name_{normalize(location_name)}"

        # add an event
        event["location_id"] = key
        
        entry = {
            "name": location_name,
            "resolved_name": location.get("resolved_name"),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
            "source": location.get("source"),
        }
        score = {"nominatim": 3, "wikidata": 2, "geonames": 1, None: 0}

        found = None

        for existing_key, existing in locations.items():
            if is_same_place(existing, entry):
                found = existing_key
                break

        score = {"nominatim": 1, "geonames": 2, "wikidata": 3, None: 0}

        if found:

            existing = locations[found]

            if score.get(entry["source"], 0) > score.get(existing["source"], 0):
                best = entry
                other = existing
            else:
                best = existing
                other = entry

            # Best font
            merged = best.copy()

            # Resolved name from richer font
            if entry.get("resolved_name") and (
                not merged.get("resolved_name") or
                len(entry.get("resolved_name")) > len(merged.get("resolved_name"))
            ):
                merged["resolved_name"] = entry.get("resolved_name")

            locations[found] = merged
            event["location_id"] = found

        else:
            locations[key] = entry
            event["location_id"] = key

        events.append(event)

    # ============================
    # EXPORT LOCATIONS JSON
    # ============================
    if write_json:
        loc_path = "data/eventi/parsed/locations.json"

        with open(loc_path, "w", encoding="utf-8") as f:
            json.dump(locations, f, ensure_ascii=False, indent=2)

        wb_loc = Workbook()
        ws = wb_loc.active
        ws.title = "locations"

        # header
        ws.append(["location_id", "name", "resolved_name", "lat", "lon", "source"])
        # righe
        for key, val in locations.items():
            ws.append([
            key,
            val["name"],
            val.get("resolved_name"),
            val["lat"],
            val["lon"],
            val["source"],
        ])

        wb_loc.save("data/eventi/parsed/locations.xlsx")

    # ============================
    # CLEAN EVENTS
    # ============================
    events = [
        e for e in events
        if any([
            e.get("event_label"),
            e.get("event_type"),
            e.get("location"),
        ])
    ]

    # ============================
    # FINAL STRUCTURE
    # ============================
    result = {
        "person": {
            "id": person_id,
            "name": person_name,
        },
        "events": events,
        "event_types": list(event_types),
    }

    # ============================
    # WRITE JSON
    # ============================
    if write_json:
        os.makedirs("data/eventi/parsed", exist_ok=True)

        fallback_name = os.path.basename(xlsx_path).replace(".xlsx", "")
        filename_id = person_id or fallback_name

        output_path = f"data/eventi/parsed/{filename_id}.events.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ==================================================
# BATCH PROCESSOR
# ==================================================
def batch_read_event_sheets(
    input_dir="data/eventi",
    output_dir="data/eventi/parsed"
):

    os.makedirs(output_dir, exist_ok=True)

    files = glob(os.path.join(input_dir, "*.xlsx"))

    results = []

    for filepath in files:
        try:
            print(f"Processing: {filepath}")

            data = read_event_sheet(filepath,  write_json=True)

            person_id = data.get("person", {}).get("id")
            fallback_name = os.path.basename(filepath).replace(".xlsx", "")

            filename_id = person_id or fallback_name

            output_path = os.path.join(
                output_dir,
                f"{filename_id}.events.json"
            )

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            results.append(output_path)

        except Exception as e:
            print(f"Error processing {filepath}: {e}")

    print(f"\n✅ Processed {len(results)} files")

    return results