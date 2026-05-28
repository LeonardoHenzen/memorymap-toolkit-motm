import requests
from urllib.parse import urlparse
import re
from typing import Optional
import time


GEONAMES_USERNAME = "mapto"

domains = ["geonames.org", "wikidata.org"]
_nominatim_cache = {}

def search_location(query, max_rows=10):
    url = "http://api.geonames.org/searchJSON"
    params = {"q": query, "maxRows": max_rows, "username": GEONAMES_USERNAME}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def extract_url_map(text: str) -> tuple[dict[str, str], str]:
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(pattern, text)
    url_map = {urlparse(u).hostname: u for u in urls}
    remaining = re.sub(pattern, "", text).strip()
    return url_map, remaining.strip()


def extract_urls(text: str) -> list[tuple[str, dict[str, str]]]:
    """
    >>> extract_urls("Allenstein")
    [('Allenstein', {})]
    """
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

    # Normalize: treat newlines as spaces
    text = text.replace("\n", " ")

    parts = re.split(pattern, text)
    urls = re.findall(pattern, text)

    pairs: list[tuple[str, dict[str, str]]] = []
    for i, substring in enumerate(parts):
        substring = substring.strip()
        if i < len(urls):
            adjacent_urls: list[str] = [urls[i]]
            while i + 1 < len(urls) and parts[i + 1].strip() == "":
                i += 1
                adjacent_urls += [urls[i]]
            url_map = {}
            for u in adjacent_urls:
                h = urlparse(u).hostname
                # assert h not in url_map, f"{h} repeated in {urls}"
                if h not in url_map:
                    url_map[h] = []
                url_map[h] += [u]
            pairs += [(substring, {k: " | ".join(v) for k, v in url_map.items()})]
        elif substring:
            pairs += [(substring, {})]

    return pairs


def extract_geonames_coordinates(url: str) -> Optional[dict]:
    """
    Extract coordinates from a GeoNames entity URL.
    e.g. https://www.geonames.org/6550600/finsterwalde.html

    Fetches the entity via the GeoNames API using the numeric ID.
    Returns dict with 'lat' and 'lng', or None if not found.

    Requires a free GeoNames account username: https://www.geonames.org/login
    """
    match = re.search(r"geonames\.org/(\d+)", url)
    if not match:
        return None

    geoname_id = match.group(1)

    response = requests.get(
        "http://api.geonames.org/getJSON",
        params={"geonameId": geoname_id, "username": GEONAMES_USERNAME},
        headers={"User-Agent": "coord-extractor/1.0"},
    )
    response.raise_for_status()
    data = response.json()

    try:
        return {
            "lat": float(data["lat"]),
            "long": float(data["lng"]),
            "name": data.get("name"),
            "adminName1": data.get("adminName1"),
            "countryName": data.get("countryName"),
        }

    except (KeyError, ValueError):
        return None


def extract_wikidata_coordinates(url: str) -> Optional[dict]:
    """
    Extract coordinates from a Wikidata entity URL.
    e.g. https://www.wikidata.org/wiki/Q64

    Fetches the entity via the Wikidata API and reads property P625 (coordinate location).
    Returns dict with 'lat' and 'lng', or None if not found.
    """
    match = re.search(r"/wiki/(Q\d+)", url)
    if not match:
        return None

    qid = match.group(1)

    response = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims|labels",
            "format": "json",
        },
        headers={"User-Agent": "coord-extractor/1.0"},
    )
    response.raise_for_status()
    data = response.json()

    try:

        entity = data["entities"][qid]
        claims = entity["claims"]
        p625 = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
        labels = entity.get("labels", {})
        label = (labels.get("en", {}).get("value") or labels.get("de", {}).get("value"))
        return {
            "lat": p625["latitude"],
            "long": p625["longitude"],
            "label": label
        }    
    except (KeyError, IndexError):
        return None


def search_nominatim(query, country_code=None):
    """
    Geocoding via OpenStreetMap Nominatim.
    Parameters:
        query (str): place name or address
        country_code (str, optional): ISO country code (e.g. "de", "it")
    Returns:
        dict or None:
            {
                "lat": float,
                "lon": float,
                "display_name": str
            }
    """
    if not query:
        return None
    time.sleep(1)
    
    cache_key = (query, country_code)

    if cache_key in _nominatim_cache:
        return _nominatim_cache[cache_key]

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
    }

    if country_code:
        params["countrycodes"] = country_code

    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "memorymap-toolkit-geocoder/1.0"},
            timeout=5
        )
        response.raise_for_status()

        results = response.json()

        if not results:
            _nominatim_cache[cache_key] = None
            return None

        best = results[0]

        result = {
            "lat": float(best["lat"]),
            "lon": float(best["lon"]),
            "display_name": best.get("display_name"),
        }

        _nominatim_cache[cache_key] = result
        return result

    except Exception as e:
        print(f"⚠️ Nominatim error for '{query}': {e}")
        _nominatim_cache[cache_key] = None
        return None
