import json
import os
import re
from glob import glob
from datetime import datetime
from openpyxl import load_workbook


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

    # nome (prima cella non vuota)
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
    locations = {}
    event_types = set()

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
        # LOCATION
        # ------------------------
        location_name = clean_value(data.get("place_name"))

        if location_name:

            loc = locations.setdefault(
                location_name,
                {
                    "current_name": location_name,
                    "wikidata_id": clean_value(data.get("wikidata_qid")),
                    "geonames_id": clean_value(data.get("geonames_id")),
                    "google_maps": clean_value(data.get("google maps")),
                }
            )

            event["location"] = location_name

        # ------------------------
        # EXTERNAL LINKS
        # ------------------------
        links_raw = clean_value(data.get("external_links"))

        if links_raw:
            event["external_links"] = [
                link.strip()
                for link in links_raw.split("\n")
                if link.strip()
            ]

        events.append(event)

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
        "locations": list(locations.values()),
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

            data = read_event_sheet(filepath)

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
            print(f"❌ Error processing {filepath}: {e}")

    print(f"\n✅ Processed {len(results)} files")

    return results