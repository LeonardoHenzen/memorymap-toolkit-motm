from django.shortcuts import render

from django.http import JsonResponse
from mmt_motm.importers.geojson_export import export_geojson

# =======================================================
# View of geodata in json format 
# =======================================================
def geojson_view(request):

    # Person
    identifiers = request.GET.get("person")

    if identifiers:
        identifiers = identifiers.split(",")
    else:
        identifiers = None

    data = export_geojson(identifiers=identifiers)

    return JsonResponse(data, safe=False)