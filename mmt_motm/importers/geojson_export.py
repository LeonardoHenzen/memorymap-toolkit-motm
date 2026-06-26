# =======================================================
# Function for extracting geodata in json from DB to MM 
# =======================================================
from mmt_motm.models import Event, Person
from mmt_map.import_geojson import import_geojson  
from mmt_map.models import Point, Line, Theme

# =======================================================
# Extraction of geodata in json format from DB 
# =======================================================
def export_geojson(identifiers=None):

    if identifiers and not isinstance(identifiers, (list, tuple, set)):
        identifiers = [identifiers]

    if identifiers:
        persons = list(Person.objects.filter(identifier__in=identifiers))
    else:
        persons = None

    events = Event.objects.select_related(
        "event_type", "start_location"
    ).prefetch_related("persons")

    if persons:
        events = events.filter(persons__in=persons).distinct()

    events = list(events)

    features = []

    # POINTS
    for e in events:
        loc = e.start_location
        if not loc or not loc.location:
            continue

        person_obj = e.persons.first()

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [loc.location.x, loc.location.y]
            },
            "properties": {
                "type": "event",
                "person": person_obj.identifier if person_obj else None,
                "name": str(person_obj) if person_obj else None,
                "category": e.event_type.category if e.event_type else None,
                "event_type": e.event_type.code if e.event_type else None,
                "label": e.event_label,
                "date": (
                    e.start_time.isoformat()
                    if e.start_time else e.date_original
                ),
            }
        })

    # LINES
    if persons:
        persons_set = persons
    else:
        persons_set = list(set(p for e in events for p in e.persons.all()))

    for p in persons_set:
        p_events = [e for e in events if p in e.persons.all()]
        features += build_lines_for_person(p, p_events)

    return {
        "type": "FeatureCollection",
        "features": features
    }


def build_lines_for_person(person, events):

    events_sorted = sorted(events, key=lambda e: e.id)

    lines = []
    last_by_category = {}

    for e in events:

        loc = e.start_location
        if not loc or not loc.location:
            continue

        cat = e.event_type.category if e.event_type else None
        if not cat:
            continue

        coord = [loc.location.x, loc.location.y]

        if cat in last_by_category:
            prev = last_by_category[cat]


            if not prev or not coord or prev == coord:
                last_by_category[cat] = coord
                continue

            line = [prev, coord]

            if len(line) < 2:
                continue
                
            lines.append({
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [prev, coord]
                    ]
                },
                "properties": {
                    "type": "path",
                    "person": person.identifier,
                    "category": cat,
                    "label": cat
                }
            })

        last_by_category[cat] = coord

    return lines

def delete_person_from_mm(identifier):

    try:
        theme = Theme.objects.get(name=identifier)
    except Theme.DoesNotExist:
        return

    Point.objects.filter(theme=theme).delete()
    Line.objects.filter(theme=theme).delete()

# =======================================================
# Importing geodata in MM (Theme, Points,Lines) 
# =======================================================
def sync_to_mm(identifiers=None):

    if identifiers and not isinstance(identifiers, (list, tuple, set)):
        identifiers = [identifiers]

    # PERSON Extraction
    if identifiers:
        persons = Person.objects.filter(identifier__in=identifiers)
    else:
        persons = Person.objects.all()

    for p in persons:
        sync_person_to_mm(p.identifier)

def sync_person_to_mm(identifier):

    # Delete if exist
    delete_person_from_mm(identifier)

    # Import new from endpoint
    import_geojson(
        url=f"http://localhost:8000/geojson/?person={identifier}",
        feature_title="label",
        doc_title="Event",
        fallback="Event",
        theme="person"
    )
