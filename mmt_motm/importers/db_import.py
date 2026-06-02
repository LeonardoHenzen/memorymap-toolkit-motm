# =======================================================
# Function for loading json file metadati/parsed in DB
# =======================================================
import os
import json

from django.contrib.gis.geos import Point
from datetime import datetime
from django.utils.timezone import make_aware
from django.utils.timezone import is_naive

from mmt_motm.models import (
    Person, 
    Interview, 
    Relationship, 
    LocationPoint, 
    LocationRegion, 
    RelationshipType,
    LocationPoint,
    EventType,
    Event,
    URL,
)

# =======================================================
# UTILS
# =======================================================
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def is_empty(value):
    return value in [None, "", "-", "–", "—"]

def parse_name(full_name):

    if not full_name:
        return None, None

    full_name = full_name.strip()

    # "Surname, Name"
    if "," in full_name:
        parts = full_name.split(",")

        family_name = parts[0].strip()
        given_name = parts[1].strip() if len(parts) > 1 else "UNKNOWN"

        return given_name, family_name

    # "Name Surname"
    parts = full_name.split()

    if len(parts) > 1:
        given_name = parts[0]
        family_name = " ".join(parts[1:])
        return given_name, family_name

    return full_name, "UNKNOWN"

# Regions hierarchy
def get_or_create_region_hierarchy(region_list):
    if not region_list:
        return None

    parent = None

    for name in region_list:
        if is_empty(name):
            continue

        region = LocationRegion.objects.filter(name=name).first()

        if not region:
            region = LocationRegion.objects.create(name=name)

        if parent and region.part_of != parent:
            region.part_of = parent
            region.save()

        parent = region

    return parent

def clean_label(label):

    label = label.strip().lower()
    label = label.replace("(", "").replace(")", "")
    label = label.replace(".", "")
    label = " ".join(label.split())

    return label

RELATIONSHIP_MAP = {
        "vater": "father",
        "mutter": "mother",
        "schwester": "sister",
        "bruder": "brother",
        "großvater": "grandfather",
        "grossvater": "grandfather",
        "großvater väterlicherseits": "paternal grandfather",
        "grossvater väterlicherseits": "paternal grandfather",
        "großvater väterl": "paternal grandfather",
        "großmutter väterlicherseits": "paternal grandmother",
        "großmutter väterl": "paternal grandmother",
        "grossmutter väterlicherseits": "paternal grandmother",
        "großmutter mütterlicherseits": "maternal grandmother",
        "grossmutter mütterlicherseits": "maternal grandmother",
        "großmutter mütt": "maternal grandmother",
        "großvater mütterlicherseits": "maternal grandfather",
        "großvater mütt": "maternal grandfather",
        "tante": "aunt",
        "onkel": "uncle",
        "onkel väterl": "paternal uncle",
        "bruder aus erster ehe": "brother from the first marriage",
        "halbschwester": "half sister",
        "1 frau erste ehe": "first wife",
        "stiefmutter": "stepmother",
        "cousin": "cousin",
        "vetter": "cousin",
        "cousine": "cousin",
        "base": "cousin",
}

def parse_event_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        return make_aware(dt)
    except Exception:
        return None

# =======================================================
# PERSON MATCHING
# =======================================================
def get_or_create_person(data, identifier=None):

    given_name = data.get("given_name")
    family_name = data.get("family_name")
    birth_date = data.get("birth_date")

    # no data → skip
    if is_empty(given_name) and is_empty(family_name):
        return None

    # MATCH ON IDENTIFIER
    if identifier:
        person = Person.objects.filter(identifier=identifier).first()
        if person:
            return person

        return Person.objects.create(
            identifier=identifier,
            given_name=given_name,
            family_name=family_name,
            birth_date=birth_date,
            gender=data.get("gender"),
            description=data.get("attributes", {}).get("ns_persecution_group"),
        )

    # MATCH on name + surname + birth_date
    if not is_empty(given_name) and not is_empty(family_name) and birth_date:
        person = Person.objects.filter(
            given_name=given_name,
            family_name=family_name,
            birth_date=birth_date
        ).first()

        if person:
            return person

    # MATCH on name + surname
    if not is_empty(given_name) and not is_empty(family_name):
        person = Person.objects.filter(
            given_name=given_name,
            family_name=family_name
        ).first()

        if person:
            return person

    return Person.objects.create(
        given_name=given_name,
        family_name=family_name,
        birth_date=birth_date
    )


# =======================================================
# LOCATION
# =======================================================
def get_or_create_location(bp):

    if is_empty(bp.get("name")):
        return None

    location = LocationPoint.objects.filter(
        current_name=bp["name"]
    ).first()

    # Region update
    if location:

        if not location.region:   
            regions = bp.get("regions") or []

            parent = None
            for name in regions:
                if is_empty(name):
                    continue

                region = LocationRegion.objects.filter(name=name).first()

                if not region:
                    region = LocationRegion.objects.create(name=name)

                if parent and region.part_of != parent:
                    region.part_of = parent
                    region.save()

                parent = region

            if parent:
                location.region = parent
                location.save()

        return location

    point = None
    if bp.get("coordinates"):
        lat = bp["coordinates"].get("lat")
        lon = bp["coordinates"].get("lon")

        if lat is not None and lon is not None:
            point = Point(lon, lat)

    location = LocationPoint.objects.create(
        current_name=bp["name"],
        location=point,
        wikidata_id=bp.get("wikidata_id"),
    )

    regions = bp.get("regions") or []

    parent = None
    for name in regions:
        if is_empty(name):
            continue

        region = LocationRegion.objects.filter(name=name).first()

        if not region:
            region = LocationRegion.objects.create(name=name)

        if parent and region.part_of != parent:
            region.part_of = parent
            region.save()

        parent = region

    if parent:
        location.region = parent
        location.save()

    return location

# =======================================================
# INTERVIEW 
# =======================================================
def create_interview(person, data):

    # No archive_id → skip
    if is_empty(data.get("archive_id")):
        return None

    archive_id = data["archive_id"]

    existing = Interview.objects.filter(
        archive_id=archive_id
    ).first()

    if existing:
        return existing

    interviewer = None

    if not is_empty(data.get("interviewer")):
        given, family = parse_name(data["interviewer"])

        interviewer = get_or_create_person({
            "given_name": given,
            "family_name": family
        })

    return Interview.objects.create(
        archive_id=archive_id,
        interviewee=person,
        interviewer=interviewer,
        interview_type=data.get("type") or "",
        date=data.get("date"),
        place=data.get("place") or "",
        description=""  # se vuoi puoi mettere type o altro
    )

# =======================================================
# RELATIONSHIP 
# =======================================================
def get_or_create_relationship_type(label):

    if is_empty(label):
        return None

    label_original = label.strip()
    label_clean = clean_label(label)

    mapped = RELATIONSHIP_MAP.get(label_clean, label_clean)

    rt = RelationshipType.objects.filter(name=mapped).first()

    if rt:
        return rt

    return RelationshipType.objects.create(
        name=mapped,
        original_label=label_original
    )

def create_relationship(main_person, data, fallback_family_name):

    if is_empty(data.get("relation")):
        return None

    given_name = data.get("given_name")
    family_name = data.get("family_name")

    # Fallback surname
    if is_empty(family_name):
        family_name = fallback_family_name

    related = get_or_create_person({
        "given_name": given_name,
        "family_name": family_name,
        "birth_date": data.get("birth_date")
    })

    if not related:
        return None

    rel_type = get_or_create_relationship_type(data.get("relation"))

    if not rel_type:
        return None

    # Check
    exists = Relationship.objects.filter(
        person_from=main_person,
        person_to=related,
        relationship_type=rel_type
    ).exists()

    if exists:
        return None

    return Relationship.objects.create(
        relationship_type=rel_type,
        person_from=main_person,
        person_to=related,
        description=data.get("notes") or ""
    )

# =======================================================
# IMPORT RECORD
# =======================================================
def import_record(record):

    # PERSON primary
    person = get_or_create_person(
        record["person"],
        identifier=record.get("identifier")
    )

    if not person:
        print("Skipped: invalid person")
        return None

    # LOCATION (birth_place)
    location = get_or_create_location(record["birth_place"])

    if location:
        person.birth_place = location
        person.save()

    # INTERVIEWS
    for i in record["interviews"]:
        create_interview(person, i)

    # FAMILY
    main_family_name = person.family_name
    for f in record["family"]:
        create_relationship(person, f, main_family_name)

    return person

# =======================================================
# IMPORT FILE
# =======================================================
def import_from_file(path):

    record = load_json(path)

    person = import_record(record)

    if person:
        print(f"✅ Imported: {path}")
    else:
        print(f"⚠️ Skipped: {path}")

    return person

# =======================================================
# IMPORT ALL METADATI FILES
# =======================================================
def import_all(directory="data/parsed"):

    results = []

    for filename in os.listdir(directory):

        if not filename.endswith(".json"):
            continue

        path = os.path.join(directory, filename)

        try:
            person = import_from_file(path)

            if person:
                results.append(person)

        except Exception as e:
            print(f"❌ ERROR in {filename}: {e}")

    print(f"\n✅ Imported {len(results)} valid records")

    return results

# ==========================================================
# IMPORT Locations from JSON into DB
# NB: Returns a cache: {location_id: LocationPoint instance}
# ==========================================================
def import_locations(locations_dict):

    cache = {}

    for loc_id, data in locations_dict.items():

        # ==========================
        # EXTRACT IDS
        # ==========================
        wikidata_id = None
        geonames_id = None

        if loc_id.startswith("wd_"):
            wikidata_id = loc_id.replace("wd_", "")

        elif loc_id.startswith("geo_"):
            geonames_id = loc_id.replace("geo_", "")

        # ==========================
        # MATCH EXISTING
        # ==========================
        location = None

        if wikidata_id:
            location = LocationPoint.objects.filter(
                wikidata_id=wikidata_id
            ).first()

        elif geonames_id:
            location = LocationPoint.objects.filter(
                geonames_id=geonames_id
            ).first()

        # fallback (by name)
        if not location and data.get("name"):
            location = LocationPoint.objects.filter(
                current_name=data["name"]
            ).first()

        lat = data.get("lat")
        lon = data.get("lon")

        point = None
        if lat is not None and lon is not None:
            point = Point(lon, lat)

        current_name = data.get("name")
        postal_address = data.get("resolved_name") or ""

        # ---- alternate names ----
        alt_names = []
        if data.get("name") and data.get("resolved_name"):
            if data["name"] not in data["resolved_name"]:
                alt_names.append(data["name"])

        alternate_names = "; ".join(alt_names) if alt_names else ""

        source = data.get("source")
        description_parts = []
        if source:
            description_parts.append(f"source: {source}")

        if wikidata_id:
            description_parts.append(f"wikidata: {wikidata_id}")
        if geonames_id:
            description_parts.append(f"geonames: {geonames_id}")

        description = " | ".join(description_parts)

        # ==========================
        # CREATE IF NOT EXISTS
        # ==========================
        if not location:

            location = LocationPoint.objects.create(
                current_name=current_name,
                postal_address = data.get("resolved_name") or "",
                alternate_names=alternate_names,
                description=description,
                location=point,
                wikidata_id=wikidata_id,
                geonames_id=geonames_id,
            )

        else:
            # ==========================
            # UPDATE EXISTING (safe enrich)
            # ==========================
            updated = False

            # coordinates
            if not location.location and point:
                location.location = point
                updated = True

            # postal address
            if not location.postal_address and postal_address:
                location.postal_address = postal_address
                updated = True

            # identifiers
            if wikidata_id and not location.wikidata_id:
                location.wikidata_id = wikidata_id
                updated = True

            if geonames_id and not location.geonames_id:
                location.geonames_id = geonames_id
                updated = True

            # description (append if new info)
            if description:
                existing_desc = location.description or ""
                if description not in existing_desc:
                    location.description = (
                        existing_desc + " | " + description
                        if existing_desc else description
                    )
                    updated = True

            if updated:
                location.save()

        # ==========================
        # CACHE
        # ==========================
        cache[loc_id] = location

    return cache

# ==========================================================
# IMPORT Events type from JSON into DB
# ==========================================================
def get_or_create_event_type(code):

    if not code:
        return None
    code_clean = code.lower().strip()
    obj, _ = EventType.objects.get_or_create(
        code=code_clean,
        defaults={"label": code_clean}
    )
    return obj

# ==========================================================
# IMPORT Events from JSON into DB
# ==========================================================
from datetime import datetime

from mmt_motm.models import Event, EventType, URL


# ==========================
# DATE PARSER (STRICT)
# ==========================
def parse_event_date(date_str):

    if not date_str:
        return None

    try:
        # accetta SOLO date complete (YYYY-MM-DD)
        return datetime.fromisoformat(date_str)
    except:
        return None


# ==========================
# EVENT TYPE
# ==========================
def get_or_create_event_type(code):

    if not code:
        return None

    code_clean = code.lower().strip()

    obj, _ = EventType.objects.get_or_create(
        code=code_clean,
        defaults={"label": code_clean.capitalize()}
    )

    return obj


# ==========================
# IMPORT EVENTS
# ==========================
def import_events(events, location_cache, person):

    results = []
    for ev in events:

        # DATE
        start_time = parse_event_date(ev.get("date"))
        start_time = (make_aware(start_time) if start_time and is_naive(start_time) else start_time)

        date_original = ev.get("date_original") or ""
        is_confirmed = ev.get("date_certainty") == "certain"

        # LOCATION
        location_id = ev.get("location_id")
        location = location_cache.get(location_id)
        if not location:
            print("Missing location:", location_id)
            
        # EVENT TYPE
        event_type = get_or_create_event_type(ev.get("event_type"))

        # LABEL (short description)
        event_label = ev.get("event_label") or ""

        # DESCRIPTION (note + extra)
        desc_parts = []
        if ev.get("notes"):
            desc_parts.append(ev["notes"])

        description = " | ".join(desc_parts)
        
        if start_time:
            existing = Event.objects.filter(
                persons=person,
                event_type=event_type,
                start_time=start_time,
                start_location=location,
            ).first()
        else:
            existing = Event.objects.filter(
                persons=person,
                event_type=event_type,
                start_time__isnull=True,
                date_original=date_original,
                start_location=location,
            ).first()

        # CREATE EVENT
        if existing:
            event = existing
            
            # ---- PERSON ----
            if person not in event.persons.all():
                event.persons.add(person)

            # ---- URLS (merge) ----
            for url in ev.get("external_links", []):
                url_obj, _ = URL.objects.get_or_create(url=url)
                if url_obj not in event.urls.all():
                    event.urls.add(url_obj)

            # ---- DESCRIPTION (merge soft) ----
            if description and description not in (event.description or ""):
                event.description = (
                    (event.description or "") + " | " + description
                ).strip(" | ")
                event.save()

        else:
            event = Event.objects.create(
                start_time=start_time,
                date_original=date_original,
                description=description,
                event_label=event_label,
                event_type=event_type,
                place_type=ev.get("place_type") or "",
                place_category=ev.get("place_category") or "",
                start_location=location,
                is_confirmed=is_confirmed,
            )

            # PERSON LINK
            event.persons.add(person)

            # URLS
            for url in ev.get("external_links", []):
                url_obj, _ = URL.objects.get_or_create(url=url)
                event.urls.add(url_obj)

        results.append(event)

    return results

# =====================================
# IMPORT EVENTS FILES: Location, Event
# =====================================
def import_events_file(events_path, locations_path):

    events_data = load_json(events_path)
    locations_data = load_json(locations_path)

    try:
        # PERSON
        person_data = events_data.get("person", {})
        identifier = person_data.get("id")
        if not identifier:
            print("Missing person id")
            return None
        try:
            # Person mast exixt in DB
            person = Person.objects.get(identifier=identifier)
        except Person.DoesNotExist:
            print(f"Person not found: {identifier}")
            return None

        # LOCATIONS 
        location_cache = import_locations(locations_data)

        # EVENTS
        events = events_data.get("events", [])
        event_objs = import_events(events, location_cache, person)

        print(f"Imported {len(event_objs)} events")

        events_new_path = events_path.replace(".json", "_loaded.json")
        locations_new_path = locations_path.replace(".json", "_loaded.json")

        os.rename(events_path, events_new_path)
        os.rename(locations_path, locations_new_path)

        return event_objs

    except Exception as e:
        print(f"ERROR: {e}")
        return None
    
"""
# Just for Location import test
def test_import_locations(path="data/eventi/parsed/locations.json"):

    data = load_json(path)

    print(f"Loading {len(data)} locations...\n")

    cache = import_locations(data)

    print("\n--- SAMPLE CHECK ---")

    for i, (loc_id, loc) in enumerate(cache.items()):
        if i >= 10:
            break

        print(f"\nID: {loc_id}")
        print(f"  current_name: {loc.current_name}")
        print(f"  postal_address: {loc.postal_address}")
        print(f"  wikidata_id: {loc.wikidata_id}")
        print(f"  geonames_id: {loc.geonames_id}")
        print(f"  location: {loc.location}")
        print(f"  description: {loc.description}")

    print("\n✅ Test completed.")

    return cache
"""