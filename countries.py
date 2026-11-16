"""Download country points from Wikidata (CC0) into data/countries.json.

The game needs one point per country to score a guess by distance,
like GeoGuessr. Wikidata's "coordinate location" (P625) of a country is
a point inside it. Run once: python countries.py
"""

import json
import urllib.parse
import urllib.request

SPARQL_URL = "https://query.wikidata.org/sparql"
OUT_PATH = "data/countries.json"
LEADERS_RAW = "data/raw/leaders_raw.json"

QUERY = """
SELECT ?code3 ?name (SAMPLE(?coord) AS ?point) (SAMPLE(?contName) AS ?continent) WHERE {
  ?country wdt:P31 wd:Q3624078 ; wdt:P298 ?code3 ; wdt:P625 ?coord .
  FILTER NOT EXISTS { ?country wdt:P576 [] }
  ?country rdfs:label ?name . FILTER(LANG(?name) = "en")
  OPTIONAL { ?country wdt:P30 ?cont . ?cont rdfs:label ?contName . FILTER(LANG(?contName) = "en") }
} GROUP BY ?code3 ?name
"""


def run_query(query):
    """Send a SPARQL query to Wikidata and return the result rows."""
    url = SPARQL_URL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": "PoliticianGuesser/1.0 (student project)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["results"]["bindings"]


def parse_point(wkt):
    """Turn Wikidata's 'Point(lon lat)' text into (lat, lon)."""
    lon, lat = wkt.removeprefix("Point(").removesuffix(")").split()
    return float(lat), float(lon)


def known_continents():
    """Continent per country as the download block already chose it."""
    try:
        with open(LEADERS_RAW, encoding="utf-8") as f:
            return {row["country_code3"]: row["continent"] for row in json.load(f)}
    except FileNotFoundError:
        return {}


def main():
    continents = known_continents()
    countries = {}
    for row in run_query(QUERY):
        code3 = row["code3"]["value"]
        lat, lon = parse_point(row["point"]["value"])
        countries[code3] = {
            "code3": code3,
            "name": row["name"]["value"],
            "lat": round(lat, 3),
            "lon": round(lon, 3),
            "continent": continents.get(code3) or row.get("continent", {}).get("value", "Unknown"),
        }
    # The Kingdom of Denmark has no P625 point on Wikidata; use mainland Denmark (Q35).
    countries.setdefault("DNK", {"code3": "DNK", "name": "Denmark", "lat": 56.0, "lon": 10.0, "continent": "Europe"})
    result = sorted(countries.values(), key=lambda c: c["name"])
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(result)} countries to {OUT_PATH}")


if __name__ == "__main__":
    main()
