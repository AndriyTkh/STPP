"""Download the raw data for Politician Guesser. Nothing is cleaned here.

Sources: Wikidata (CC0), Wikimedia Commons (per-file licences), en.wikiquote
(CC BY-SA) and the CIA World Leaders list via OpenSanctions.

Output (input for clean.py):
  data/raw/leaders_raw.json       one object per current leader + country facts
  data/raw/wikiquote.json         {QID: {"title": ..., "wikitext": ...}}
  data/raw/cia_world_leaders.csv  CIA World Leaders list, exactly as downloaded
  data/img/<QID>.<ext>            300 px photos
  data/SOURCES.md                 sources, licences, retrieval date, queries

Every HTTP response is cached in .cache/, so a re-run does not touch the
network. Standard library only.

Usage: python download.py
"""
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
IMG = DATA / "img"
CACHE = Path(os.environ.get("STPP_BUILD_CACHE", ROOT / ".cache"))

USER_AGENT = ("STPP-politician-guesser/0.1 "
              "(https://github.com/AndriyTkh/STPP; CS201 student hackathon)")
SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIQUOTE_API = "https://en.wikiquote.org/w/api.php"
CIA_URL = ("https://data.opensanctions.org/datasets/latest/"
           "us_cia_world_leaders/targets.simple.csv")

WIKIMEDIA_DELAY = 1.2      # seconds between live Wikimedia calls
MAX_RETRIES = 3            # retries on HTTP 429
WIKIQUOTE_MAX_BYTES = 6_000_000   # above this, wikiquote.json is trimmed

STATS = {"network": 0, "cached": 0, "http_429": 0, "failures": []}
_last_wikimedia_call = 0.0

# --------------------------------------------------------------------------
# SPARQL queries
# --------------------------------------------------------------------------

HEADS_QUERY = """SELECT ?person ?name ?country ?image ?birth ?wikiquote ?sitelinks ?start ?rank WHERE {
  ?country wdt:P31 wd:Q3624078 ; p:%(prop)s ?st .
  ?st ps:%(prop)s ?person ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  FILTER NOT EXISTS { ?st pq:P582 [] }
  FILTER NOT EXISTS { ?country wdt:P576 [] }
  FILTER NOT EXISTS { ?person wdt:P570 [] }
  ?person wdt:P31 wd:Q5 ; wdt:P18 ?image ; wikibase:sitelinks ?sitelinks .
  ?person rdfs:label ?name . FILTER(LANG(?name) = "en")
  OPTIONAL { ?st pq:P580 ?start . }
  OPTIONAL { ?person wdt:P569 ?birth . }
  OPTIONAL { ?wikiquote schema:about ?person ; schema:isPartOf <https://en.wikiquote.org/> . }
}"""

COUNTRIES_QUERY = """SELECT ?country ?countryName (SAMPLE(?iso) AS ?iso2) (SAMPLE(?iso3v) AS ?iso3)
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
} GROUP BY ?country ?countryName"""

ROLES = {"P35": "head of state", "P6": "head of government"}

# Sovereign states whose ISO codes sit on a constituent country item instead.
ISO2_FALLBACK = {"Q756617": "DK"}   # Kingdom of Denmark -> Denmark
ISO3_FALLBACK = {"Q756617": "DNK"}

# Sections we never use (quotes ABOUT the person, disputed quotes, links).
# Only applied when wikiquote.json would be larger than WIKIQUOTE_MAX_BYTES.
STOP_SECTION = re.compile(
    r"^==\s*(Disputed|Misattributed|Quotes about|About|External links|See also|"
    r"Sourced quotes about|Attributed)", re.I)

# --------------------------------------------------------------------------
# HTTP with cache, polite delay and 429 handling
# --------------------------------------------------------------------------


def cache_path(url):
    """Return the cache file for a URL (sha1 of the URL)."""
    return CACHE / hashlib.sha1(url.encode("utf-8")).hexdigest()


def fetch(url, wikimedia=True, accept=None):
    """GET a URL, using the on-disk cache first.

    Live Wikimedia calls are spaced by WIKIMEDIA_DELAY seconds and an HTTP 429
    is retried up to MAX_RETRIES times, honouring Retry-After.
    """
    global _last_wikimedia_call
    path = cache_path(url)
    if path.exists():
        STATS["cached"] += 1
        return path.read_bytes()
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    for attempt in range(MAX_RETRIES + 1):
        if wikimedia:
            wait = WIKIMEDIA_DELAY - (time.monotonic() - _last_wikimedia_call)
            if wait > 0:
                time.sleep(wait)
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == MAX_RETRIES:
                raise
            STATS["http_429"] += 1
            retry_after = err.headers.get("Retry-After", "10")
            delay = int(retry_after) if retry_after.isdigit() else 10
            print(f"  429, sleeping {delay}s ({url[:80]})")
            time.sleep(delay)
        finally:
            if wikimedia:
                _last_wikimedia_call = time.monotonic()
    STATS["network"] += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def fetch_json(url):
    """GET a URL and parse the body as JSON."""
    return json.loads(fetch(url))


def sparql(query):
    """Run a SPARQL query on the Wikidata Query Service and return the bindings."""
    url = SPARQL_URL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    rows = fetch_json(url)["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def qid(uri):
    """Extract the QID from a Wikidata entity URI."""
    return uri.rsplit("/", 1)[-1]


def write_json(path, value):
    """Write a value as readable UTF-8 JSON and return the file size in bytes."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    return path.stat().st_size


# --------------------------------------------------------------------------
# Step 1: current leaders and country facts (Wikidata)
# --------------------------------------------------------------------------


def split_values(value):
    """Split a GROUP_CONCAT value into a sorted list without empties."""
    return sorted({v.strip() for v in (value or "").split("|") if v.strip()})


def normalise_continent(label):
    """Map Wikidata continent labels to a small fixed set."""
    if not label:
        return None
    if "Oceania" in label or "Australia" in label:
        return "Oceania"
    return label


def fetch_countries():
    """Fetch sovereign states with ISO codes, capital, demonyms, continent and aliases."""
    countries = {}
    for row in sparql(COUNTRIES_QUERY):
        capitals = split_values(row.get("capitals"))
        continents = split_values(row.get("continents"))
        cap_continents = split_values(row.get("capitalContinents"))
        # A transcontinental country gets the continent of its capital.
        if len(continents) == 1:
            continent = continents[0]
        elif cap_continents:
            continent = cap_continents[0]
        else:
            continent = continents[0] if continents else None
        name = row["countryName"]
        country_qid = qid(row["country"])
        aliases = [name] + [s for s in split_values(row.get("shortNames")) if s != name]
        countries[country_qid] = {
            "country": name,
            "country_code": row.get("iso2") or ISO2_FALLBACK.get(country_qid),
            "country_code3": row.get("iso3") or ISO3_FALLBACK.get(country_qid),
            "capital": capitals[0] if capitals else None,
            "continent": normalise_continent(continent),
            "demonyms": split_values(row.get("demonyms")),
            "country_aliases": aliases,
        }
    return countries


def fetch_head_rows(prop):
    """Fetch current (no end time) holders of P35 or P6 with a photo."""
    rows = sparql(HEADS_QUERY % {"prop": prop})
    for row in rows:
        row["prop"] = prop
    return rows


def collapse_people(rows):
    """Group SPARQL rows into one record per (person, country, office)."""
    holders = {}
    for row in rows:
        key = (qid(row["person"]), qid(row["country"]), row["prop"])
        rec = holders.setdefault(key, {
            "id": key[0], "country_qid": key[1], "prop": key[2],
            "name": row["name"], "images": [], "birth_years": set(),
            "wikiquote": None, "sitelinks": int(row["sitelinks"]),
            "preferred": False, "start": "",
        })
        if row["image"] not in rec["images"]:
            rec["images"].append(row["image"])
        if row.get("birth", "")[:4].isdigit():
            rec["birth_years"].add(int(row["birth"][:4]))
        if row.get("wikiquote"):
            rec["wikiquote"] = row["wikiquote"]
        if row.get("rank", "").endswith("PreferredRank"):
            rec["preferred"] = True
        rec["start"] = max(rec["start"], row.get("start", ""))
    return list(holders.values())


def select_leaders(holders):
    """Apply the selection rules and return one entry per person.

    - drop people who hold an office in more than one country (e.g. Charles III);
    - keep at most one head of state and one head of government per country
      (preferred rank, then latest start date, then most sitelinks);
    - a person who is both head of state and of government is kept once,
      as head of state.
    """
    countries_of = {}
    for h in holders:
        countries_of.setdefault(h["id"], set()).add(h["country_qid"])
    multi = {pid for pid, cs in countries_of.items() if len(cs) > 1}
    dropped = sorted({(h["name"], len(countries_of[h["id"]])) for h in holders if h["id"] in multi})

    best = {}
    for h in holders:
        if h["id"] in multi:
            continue
        slot = (h["country_qid"], h["prop"])
        rank = (h["preferred"], h["start"], h["sitelinks"])
        if slot not in best or rank > best[slot][0]:
            best[slot] = (rank, h)
    displaced = sorted(h["name"] for h in holders
                       if h["id"] not in multi and best[(h["country_qid"], h["prop"])][1] is not h)

    by_person = {}
    for _, h in sorted(best.values(), key=lambda x: x[1]["prop"] != "P35"):
        by_person.setdefault(h["id"], h)  # P35 entries come first
    return list(by_person.values()), dropped, displaced


# --------------------------------------------------------------------------
# Step 2: CIA World Leaders list (saved as is; clean.py does the cross-check)
# --------------------------------------------------------------------------


def save_cia_csv():
    """Download the CIA World Leaders CSV (OpenSanctions) and save it unchanged."""
    raw = fetch(CIA_URL, wikimedia=False)
    (RAW / "cia_world_leaders.csv").write_bytes(raw)
    return len(raw)


# --------------------------------------------------------------------------
# Step 3: photos from Wikimedia Commons
# --------------------------------------------------------------------------


def commons_title(image_url):
    """'File:...' title from a Special:FilePath URL."""
    return "File:" + urllib.parse.unquote(image_url.rsplit("/", 1)[-1])


def strip_html(text):
    """Remove HTML tags and entities, collapse whitespace."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip() or None


def fetch_image_info(titles):
    """Query Commons imageinfo (300 px thumb URL, licence, artist) for <= 50 titles."""
    url = COMMONS_API + "?" + urllib.parse.urlencode({
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 300,
        "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl",
        "format": "json", "formatversion": 2})
    data = fetch_json(url)["query"]
    rename = {m["from"]: m["to"] for m in data.get("normalized", [])}
    info = {}
    for page in data.get("pages", []):
        if page.get("imageinfo"):
            info[page["title"]] = page["imageinfo"][0]
    return {t: info.get(rename.get(t, t)) for t in titles}


def add_photos(leaders):
    """Download a ~300 px thumbnail per leader and record licence metadata."""
    IMG.mkdir(parents=True, exist_ok=True)
    titles = {l["id"]: commons_title(l["images"][0]) for l in leaders}
    unique = sorted(set(titles.values()))
    info = {}
    for start in range(0, len(unique), 50):
        try:
            info.update(fetch_image_info(unique[start:start + 50]))
        except Exception as err:
            STATS["failures"].append(f"commons imageinfo batch {start}: {err}")
    for n, leader in enumerate(leaders, 1):
        ii = info.get(titles[leader["id"]])
        if not ii or not ii.get("thumburl"):
            STATS["failures"].append(f"no imageinfo for {leader['name']}")
            continue
        ext = Path(urllib.parse.urlparse(ii["thumburl"]).path).suffix.lower()
        ext = ".jpg" if ext in (".jpg", ".jpeg") else ext
        try:
            body = fetch(ii["thumburl"])
        except Exception as err:
            STATS["failures"].append(f"thumb {leader['name']}: {err}")
            continue
        (IMG / f"{leader['id']}{ext}").write_bytes(body)
        meta = ii.get("extmetadata", {})
        leader["image"] = f"img/{leader['id']}{ext}"
        leader["image_license"] = strip_html(meta.get("LicenseShortName", {}).get("value"))
        leader["image_artist"] = strip_html(meta.get("Artist", {}).get("value"))
        leader["image_page"] = ii.get("descriptionurl")
        if n % 25 == 0:
            print(f"  photos: {n}/{len(leaders)}")


def remove_unused_images(records):
    """Delete images in data/img left over from earlier builds."""
    used = {Path(r["image"]).name for r in records if r["image"]}
    for path in IMG.iterdir():
        if path.name not in used:
            path.unlink()


# --------------------------------------------------------------------------
# Step 4: raw page text from en.wikiquote (clean.py extracts the quotes)
# --------------------------------------------------------------------------


def wikiquote_title(url):
    """Page title from an en.wikiquote URL."""
    return urllib.parse.unquote(url.rsplit("/wiki/", 1)[-1]).replace("_", " ")


def fetch_wikitext_batch(titles):
    """Fetch wikitext for up to 20 Wikiquote titles; returns {requested title: text}."""
    url = WIKIQUOTE_API + "?" + urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": "|".join(titles), "redirects": 1,
        "format": "json", "formatversion": 2})
    data = fetch_json(url)["query"]
    rename = {t: t for t in titles}
    for step in ("normalized", "redirects"):
        mapping = {m["from"]: m["to"] for m in data.get(step, [])}
        rename = {orig: mapping.get(cur, cur) for orig, cur in rename.items()}
    texts = {}
    for page in data.get("pages", []):
        revs = page.get("revisions")
        if revs:
            texts[page["title"]] = revs[0]["slots"]["main"]["content"]
    return {orig: texts[final] for orig, final in rename.items() if final in texts}


def download_wikitext(leaders, batch_size=20):
    """Return {QID: {"title", "wikitext"}} for leaders with an en.wikiquote page."""
    todo = sorted((l for l in leaders if l["wikiquote"]), key=lambda l: -l["sitelinks"])
    pages = {}
    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        titles = [wikiquote_title(l["wikiquote"]) for l in batch]
        try:
            texts = fetch_wikitext_batch(titles)
        except Exception as err:  # keep going; quotes are optional
            STATS["failures"].append(f"wikiquote batch {start}: {err}")
            continue
        for leader, title in zip(batch, titles):
            if title not in texts:  # response was truncated: fetch this page alone
                try:
                    texts.update(fetch_wikitext_batch([title]))
                except Exception as err:
                    STATS["failures"].append(f"wikiquote {title}: {err}")
            if title in texts:
                pages[leader["id"]] = {"title": title, "wikitext": texts[title]}
        print(f"  wikiquote pages: {min(start + batch_size, len(todo))}/{len(todo)}")
    return pages


def cut_unused_sections(wikitext):
    """Cut a page at the first heading matching STOP_SECTION."""
    kept = []
    for line in wikitext.splitlines():
        if STOP_SECTION.match(line):
            break
        kept.append(line)
    return "\n".join(kept)


def save_wikiquote(pages):
    """Write wikiquote.json; trim unused sections if it is too big.

    Returns (size in bytes, size before trimming or None if not trimmed).
    """
    path = RAW / "wikiquote.json"
    size = write_json(path, pages)
    if size <= WIKIQUOTE_MAX_BYTES:
        return size, None
    for page in pages.values():
        page["wikitext"] = cut_unused_sections(page["wikitext"])
    return write_json(path, pages), size


# --------------------------------------------------------------------------
# Step 5: output
# --------------------------------------------------------------------------


def to_raw_record(leader, country):
    """Build one leaders_raw.json object: the leader plus the country facts."""
    return {
        "id": leader["id"],
        "name": leader["name"],
        "role": ROLES[leader["prop"]],
        "birth_year": min(leader["birth_years"]) if leader["birth_years"] else None,
        "sitelinks": leader["sitelinks"],
        "country": country["country"],
        "country_code": country["country_code"],
        "country_code3": country["country_code3"],
        "continent": country["continent"],
        "capital": country["capital"],
        "demonyms": country["demonyms"],
        "country_aliases": country["country_aliases"],
        "wikiquote_title": wikiquote_title(leader["wikiquote"]) if leader["wikiquote"] else None,
        "image": leader.get("image"),
        "image_license": leader.get("image_license"),
        "image_artist": leader.get("image_artist"),
        "image_page": leader.get("image_page"),
    }


def write_sources(n_leaders, n_pages):
    """Write data/SOURCES.md with sources, licences, retrieval date and queries."""
    today = date.today().isoformat()
    text = f"""# Data sources

Downloaded by `download.py` on {today}. {n_leaders} leaders in
`raw/leaders_raw.json`, {n_pages} Wikiquote pages in `raw/wikiquote.json`.
The files in `raw/` are not cleaned; `clean.py` turns them into the game data.

| Source | URL | Licence | Used for |
|---|---|---|---|
| Wikidata | {SPARQL_URL} | CC0 1.0 | leaders, offices, birth year, country facts (incl. ISO 3166-1 alpha-2 `country_code` and alpha-3 `country_code3`) in `raw/leaders_raw.json` |
| Wikimedia Commons | {COMMONS_API} | per file, see `image_license`, `image_artist`, `image_page` in `raw/leaders_raw.json` | photos in `img/` (300 px thumbnails) |
| English Wikiquote | {WIKIQUOTE_API} | CC BY-SA 4.0 (attribute: en.wikiquote.org contributors; page = leader's Wikiquote article, `wikiquote_title`) | raw page wikitext in `raw/wikiquote.json` |
| CIA World Leaders via OpenSanctions | {CIA_URL} | CIA data is US public domain; OpenSanctions packaging CC BY-NC 4.0 (non-commercial) | `raw/cia_world_leaders.csv`, unchanged, for the cross-check in `clean.py` |

Retrieval date for all sources: {today}.

Selection rules: sovereign states (Q3624078) not dissolved (no P576);
current P35/P6 statements (no P582 end time, not deprecated); living people
with a P18 image; people holding an office in more than one country are
dropped; at most one head of state and one head of government per country.

## SPARQL: current heads of state (P35); heads of government use P6

```sparql
{HEADS_QUERY % {"prop": "P35"}}
```

## SPARQL: country facts (P297 = alpha-2, P298 = alpha-3)

```sparql
{COUNTRIES_QUERY}
```
"""
    (DATA / "SOURCES.md").write_text(text, encoding="utf-8")


def main():
    """Run all download steps and print a summary."""
    sys.stdout.reconfigure(encoding="utf-8")
    RAW.mkdir(parents=True, exist_ok=True)

    print("1. Wikidata: countries and current leaders")
    countries = fetch_countries()
    holders = collapse_people(fetch_head_rows("P35") + fetch_head_rows("P6"))
    holders = [h for h in holders if h["country_qid"] in countries]
    leaders, dropped, displaced = select_leaders(holders)
    print(f"  {len(countries)} countries, {len(leaders)} leaders")
    print(f"  dropped (office in >1 country): {dropped}")
    print(f"  displaced (second holder of the same office): {displaced}")

    print("2. CIA World Leaders list (saved unchanged)")
    cia_size = save_cia_csv()
    print(f"  cia_world_leaders.csv: {cia_size} bytes")

    print("3. Photos (Commons)")
    add_photos(leaders)

    print("4. Wikiquote pages (raw wikitext)")
    pages = download_wikitext(leaders)
    quote_size, size_before = save_wikiquote(pages)
    if size_before:
        print(f"  wikiquote.json trimmed at unused sections: {size_before} -> {quote_size} bytes")
    else:
        print(f"  wikiquote.json: {quote_size} bytes")

    print("5. Write leaders_raw.json and SOURCES.md")
    records = [to_raw_record(l, countries[l["country_qid"]]) for l in leaders]
    records.sort(key=lambda r: (r["country"], r["role"]))
    write_json(RAW / "leaders_raw.json", records)
    write_sources(len(records), len(pages))
    remove_unused_images(records)

    with_photo = sum(r["image"] is not None for r in records)
    with_code3 = sum(r["country_code3"] is not None for r in records)
    print(f"Done: {len(records)} leaders, {with_photo} with photo, "
          f"{with_code3} with country_code3, {len(pages)} wikiquote pages")
    print(f"HTTP: {STATS['network']} live, {STATS['cached']} cached, "
          f"{STATS['http_429']} x 429, {len(STATS['failures'])} failures")
    for failure in STATS["failures"]:
        print("  FAIL", failure)


if __name__ == "__main__":
    main()
