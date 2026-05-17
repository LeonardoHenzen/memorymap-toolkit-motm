from django.contrib import admin
from django import forms
from django.contrib.gis.geos import Point

# Register your models here.
from .models import (
    URL,
    LocationRegion,
    LocationPoint,
    Event,
    Person,
    Relationship,
    Interview,
    RelationshipType
)

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("family_name", "given_name", "birth_date", "birth_place")
    search_fields = ("given_name", "family_name", "birth_place__current_name")
    ordering = ("family_name",)

@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("archive_id", "interviewee", "interviewer", "date", "place")
    search_fields = ("archive_id", "place",
        "interviewee__given_name",
        "interviewee__family_name",
        "interviewer__given_name",
        "interviewer__family_name")
    ordering = ("archive_id",)

# FORM with lat/lon
class LocationPointForm(forms.ModelForm):
    latitude = forms.FloatField(required=False)
    longitude = forms.FloatField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.location:
            self.fields["latitude"].initial = self.instance.location.y
            self.fields["longitude"].initial = self.instance.location.x

    def save(self, commit=True):
        instance = super().save(commit=False)

        lat = self.cleaned_data.get("latitude")
        lon = self.cleaned_data.get("longitude")

        if lat is not None and lon is not None:
            instance.location = Point(lon, lat)

        if commit:
            instance.save()
        return instance

@admin.register(LocationPoint)
class LocationPointAdmin(admin.ModelAdmin):
    form = LocationPointForm
    list_display = ("current_name", "get_latitude", "get_longitude")
    search_fields = ("current_name",)
    ordering = ("current_name",)
  
    fields = (
        "current_name",
        "latitude",     
        "longitude",
        "location",     
        "alternate_names",
        "postal_address",
        "description",
        "wikidata_id",
        "geonames_id",
        "region",
        "urls",
    )

    verbose_name = "Location"
    verbose_name_plural = "Locations"

    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None
    get_latitude.short_description = "Latitude"

    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None
    get_longitude.short_description = "Longitude"

@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ("from_person", "relationship_type", "to_person")
    search_fields = (
        "relationship_type",
        "person_from__given_name",
        "person_from__family_name",
        "person_to__given_name",
        "person_to__family_name",
    )
    ordering = ("person_from__family_name",)

    def from_person(self, obj):
        return f"{obj.person_from.given_name} {obj.person_from.family_name}"
    from_person.short_description = "From"

    def to_person(self, obj):
        return f"{obj.person_to.given_name} {obj.person_to.family_name}"
    to_person.short_description = "To"

@admin.register(LocationRegion)
class LocationRegionAdmin(admin.ModelAdmin):
    list_display = ("name", "part_of")
    search_fields = ("name",)

admin.site._registry[LocationPoint].opts.verbose_name = "Location"
admin.site._registry[LocationPoint].opts.verbose_name_plural = "Locations"

admin.site._registry[LocationRegion].opts.verbose_name = "Region"
admin.site._registry[LocationRegion].opts.verbose_name_plural = "Regions"

admin.site._registry[Person].opts.verbose_name = "Person"
admin.site._registry[Person].opts.verbose_name_plural = "People"

@admin.register(RelationshipType)
class RelationshipTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "original_label")
    ordering = ("name",)

admin.site.register(URL)
admin.site.register(Event)
