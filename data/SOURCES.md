# Data sources

Downloaded by `download.py` on 2026-11-16. 316 leaders in
`raw/leaders_raw.json`, 150 Wikiquote pages in `raw/wikiquote.json`.
The files in `raw/` are not cleaned; `clean.py` turns them into the game data.

| Source | URL | Licence | Used for |
|---|---|---|---|
| Wikidata | https://query.wikidata.org/sparql | CC0 1.0 | leaders, offices, birth year, country facts (incl. ISO 3166-1 alpha-2 `country_code` and alpha-3 `country_code3`) in `raw/leaders_raw.json` |
| Wikimedia Commons | https://commons.wikimedia.org/w/api.php | per file, see `image_license`, `image_artist`, `image_page` in `raw/leaders_raw.json` | photos in `img/` (300 px thumbnails) |
| English Wikiquote | https://en.wikiquote.org/w/api.php | CC BY-SA 4.0 (attribute: en.wikiquote.org contributors; page = leader's Wikiquote article, `wikiquote_title`) | raw page wikitext in `raw/wikiquote.json` |
| CIA World Leaders via OpenSanctions | https://data.opensanctions.org/datasets/latest/us_cia_world_leaders/targets.simple.csv | CIA data is US public domain; OpenSanctions packaging CC BY-NC 4.0 (non-commercial) | `raw/cia_world_leaders.csv`, unchanged, for the cross-check in `clean.py` |

Retrieval date for all sources: 2026-11-16.

Selection rules: sovereign states (Q3624078) not dissolved (no P576);
current P35/P6 statements (no P582 end time, not deprecated); living people
with a P18 image; people holding an office in more than one country are
dropped; at most one head of state and one head of government per country.

## SPARQL: current heads of state (P35); heads of government use P6

```sparql
SELECT ?person ?name ?country ?image ?birth ?wikiquote ?sitelinks ?start ?rank WHERE {
  ?country wdt:P31 wd:Q3624078 ; p:P35 ?st .
  ?st ps:P35 ?person ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  FILTER NOT EXISTS { ?st pq:P582 [] }
  FILTER NOT EXISTS { ?country wdt:P576 [] }
  FILTER NOT EXISTS { ?person wdt:P570 [] }
  ?person wdt:P31 wd:Q5 ; wdt:P18 ?image ; wikibase:sitelinks ?sitelinks .
  ?person rdfs:label ?name . FILTER(LANG(?name) = "en")
  OPTIONAL { ?st pq:P580 ?start . }
  OPTIONAL { ?person wdt:P569 ?birth . }
  OPTIONAL { ?wikiquote schema:about ?person ; schema:isPartOf <https://en.wikiquote.org/> . }
}
```

## SPARQL: country facts (P297 = alpha-2, P298 = alpha-3)

```sparql
SELECT ?country ?countryName (SAMPLE(?iso) AS ?iso2) (SAMPLE(?iso3v) AS ?iso3)
  (GROUP_CONCAT(DISTINCT ?capitalName; separator="|") AS ?capitals)
  (GROUP_CONCAT(DISTINCT ?capContinent; separator="|") AS ?capitalContinents)
  (GROUP_CONCAT(DISTINCT ?continentName; separator="|") AS ?continents)
  (GROUP_CONCAT(DISTINCT ?demonym; separator="|") AS ?demonyms)
  (GROUP_CONCAT(DISTINCT ?short; separator="|") AS ?shortNames) WHERE {
  ?country wdt:P31 wd:Q3624078 .
  FILTER NOT EXISTS { ?country wdt:P576 [] }
  ?country rdfs:label ?countryName . FILTER(LANG(?countryName) = "en")
  OPTIONAL { ?country wdt:P297 ?iso . }
  OPTIONAL { ?country wdt:P298 ?iso3v . }
  OPTIONAL { ?country wdt:P36 ?cap . ?cap rdfs:label ?capitalName . FILTER(LANG(?capitalName) = "en")
             OPTIONAL { ?cap wdt:P30 ?cc . ?cc rdfs:label ?capContinent . FILTER(LANG(?capContinent) = "en") } }
  OPTIONAL { ?country wdt:P30 ?cont . ?cont rdfs:label ?continentName . FILTER(LANG(?continentName) = "en") }
  OPTIONAL { ?country wdt:P1549 ?demonym . FILTER(LANG(?demonym) = "en") }
  OPTIONAL { ?country wdt:P1813 ?short . FILTER(LANG(?short) = "en") }
} GROUP BY ?country ?countryName
```
