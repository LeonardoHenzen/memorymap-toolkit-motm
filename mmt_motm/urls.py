from django.urls import path
from .views import geojson_view

urlpatterns = [
    path("geojson/", geojson_view),
]