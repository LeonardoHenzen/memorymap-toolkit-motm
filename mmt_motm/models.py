from django.contrib.gis.db import models

# This class contains all URLs used in the project
class URL(models.Model):
    url = models.URLField(unique=True)

    def __str__(self):
        return self.url
    
# This class contains all regions
class LocationRegion(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    polygon = models.MultiPolygonField(null=True, blank=True)

    wikidata_id = models.CharField(max_length=30, blank=True, null=True)
    geonames_id = models.CharField(max_length=20, blank=True, null=True)

    #To allow for a foreign key to another LocationRegion
    #allowing structures such as State > Region > City etc.
    part_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subregions"
    )

    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="regions"
    )

    def __str__(self):
        return self.name
    
# This class contains all Points part of Region
class LocationPoint(models.Model):
    
    current_name = models.CharField(max_length=100)

    # Alternative or historical names
    alternate_names = models.TextField(blank=True)

    postal_address = models.CharField(max_length=200, blank=True)

    description = models.TextField(blank=True)

    # Geographic coordinates (latitude/longitude point)
    location = models.PointField(null=True, blank=True)

    # External identifiers
    wikidata_id = models.CharField(max_length=30, blank=True, null=True)
    geonames_id = models.CharField(max_length=20, blank=True, null=True)

    # The region this point belongs to (e.g., city, state, country)
    region = models.ForeignKey(
        "LocationRegion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="points"
    )

    # Related URLs (references, sources, etc.)
    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="points"
    )

    def __str__(self):
        return self.current_name
    
# This class contains all the various Events from a person life that are registered
class Event(models.Model):
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    description = models.TextField(blank=True)

    # Source URLs or references
    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="events"
    )

    # Indicates whether the event is confirmed
    is_confirmed = models.BooleanField(default=False)

    # Starting location of the event
    start_location = models.ForeignKey(
        "LocationPoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_started"
    )

    # Ending location of the event
    end_location = models.ForeignKey(
        "LocationPoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_ended"
    )


    # Persons related to the event
    persons = models.ManyToManyField(
        "Person",
        blank=True,
        related_name="events"
    )

def __str__(self):
    if self.end_time:
        return f"Event {self.start_time} – {self.end_time}"
    return f"Event at {self.start_time}"
    
# This class contains all the People linked to the Project
class Person(models.Model):
    # External archive identifiers
    identifier = models.CharField(max_length=100, unique=True, null=True, blank=True,
    db_index=True)

    given_name = models.CharField(max_length=100)
    family_name = models.CharField(max_length=100)

    previous_given_name = models.CharField(max_length=100, blank=True)
    previous_family_name = models.CharField(max_length=100, blank=True)

    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)

    gender = models.CharField(max_length=50, blank=True)

    # Description or biography
    description = models.TextField(blank=True)

    # Place of birth
    birth_place = models.ForeignKey(
        "LocationPoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="people_born_here"
    )

    # Place of death
    death_place = models.ForeignKey(
        "LocationPoint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="people_died_here"
    )

    # Related URLs (sources, references)
    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="persons"
    )

    def __str__(self):
        return f"{self.given_name} {self.family_name}"

# This class contains all RelationshipType
class RelationshipType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    original_label = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name
        
# This class contains all Relationship among People
class Relationship(models.Model):
    
    relationship_type = models.ForeignKey(
        "RelationshipType",
        on_delete=models.CASCADE,
        related_name="relationships"
    )

    # Start and end of the relationship (if applicable)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)

    # Related URLs (sources, references)
    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="relationships"
    )

    # Person who initiates or is the source of the relationship
    person_from = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="relationships_from"
    )

    # Person who is the target of the relationship
    person_to = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="relationships_to"
    )

    def __str__(self):
        return f"{self.person_from} -> {self.relationship_type} -> {self.person_to}"


class Interview(models.Model):
    # Archive identifier (external system)
    archive_id = models.CharField(max_length=100, unique=True)

    # Recording identifier (e.g., audio/video file ID)
    recording_id = models.CharField(max_length=100, blank=True)

    interview_type = models.CharField(max_length=100, blank=True)

    date = models.DateField(null=True, blank=True)

    place = models.CharField(max_length=200, blank=True)

    description = models.TextField(blank=True)

    # Related URLs (sources, references)
    urls = models.ManyToManyField(
        "URL",
        blank=True,
        related_name="interviews"
    )

    # The person conducting the interview
    interviewer = models.ForeignKey(
        "Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interviews_conducted"
    )

    # The person being interviewed
    interviewee = models.ForeignKey(
        "Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interviews_received"
    )

    def __str__(self):
        return f"Interview {self.archive_id}"
    
    # x Martin: la classe/tabella Mention non l'ho capita bene...
