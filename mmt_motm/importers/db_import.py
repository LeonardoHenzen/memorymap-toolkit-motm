# =======================================================
# Function for loading json file metadati/parsed in DB
# =======================================================
import os
import json

from django.contrib.gis.geos import Point

from mmt_motm.models import (
    Person, 
    Interview, 
    Relationship, 
    LocationPoint, 
    LocationRegion, 
    RelationshipType,
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
# IMPORT ALL
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
