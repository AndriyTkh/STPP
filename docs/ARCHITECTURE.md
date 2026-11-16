# Politician Guesser: architecture

**The game:** you see a politician's photo and 2 of their quotes (country words hidden).
Then you get a world map and click the country they lead.

Three Python blocks, each owned by one person, connected only through files in `data/`.
Nobody imports another person's module, so commits never overlap.

```
 open sources               BLOCK 1: download         BLOCK 2: clean              BLOCK 3: game
 ------------               (Andriy)                  (Maxim)                     (Ivan Sidun)

 Wikidata SPARQL (CC0) -->  download.py          -->  clean.py              -->   game.py + app.py
 Wikimedia Commons          writes data/raw/          reads data/raw/             reads data/leaders.json
 en.wikiquote               and data/img/             writes data/leaders.json    and data/img/
 CIA World Leaders (CSV)                                                          writes data/results.csv
                                                                                        |
                                                                                        v
                                                                    PRESENTATION (Ivan Perebynis)
                                                                    stats.py -> charts/*.png
                                                                    docs/DEMO.md, slides
```

## Tech stack

| Part | Tools |
|---|---|
| Language | Python 3.11+ |
| Download | standard library only (`urllib`, `json`, `csv`, `time`) |
| Cleaning | `pandas` (join Wikidata with the CIA list, filter), `re` (quote parsing, masking) |
| Storage | plain files in `data/`: JSON, CSV, JPG. No database server |
| Game UI | `streamlit` (the whole interface is Python) |
| World map | `plotly` choropleth inside Streamlit, countries keyed by ISO alpha-3 code. Fallback if map clicks misbehave: a searchable country list (`st.selectbox`) next to the map |
| Charts | `pandas` + `matplotlib` |

## Contract 1: download -> clean

| File | Content |
|---|---|
| `data/raw/leaders_raw.json` | list of current heads of state and government, one object each (keys below) |
| `data/raw/wikiquote.json` | `{QID: {"title": ..., "wikitext": ...}}`: the raw Wikiquote page of each leader that has one |
| `data/raw/cia_world_leaders.csv` | CIA World Leaders as published: `name` (surname in CAPS), `countries` (ISO alpha-2, lower case), ... |
| `data/img/<QID>.jpg` | portrait, 300 px wide |

Keys in `leaders_raw.json`: `id`, `name`, `role`, `birth_year`, `sitelinks`, `country`,
`country_code`, `country_code3`, `continent`, `capital`, `demonyms`, `country_aliases`,
`wikiquote_title`, `image`, `image_license`, `image_artist`, `image_page`.

What `clean.py` has to do with it:
1. Keep only leaders that the CIA list confirms (same country code, surname matches). This removes stale Wikidata entries.
2. Pull English quotes out of the wikitext (40-300 characters, no wiki markup).
3. Mask giveaway words in each quote: country name and aliases -> `[COUNTRY]`, demonyms -> `[PEOPLE]`, capital -> `[CITY]`, the leader's own name -> `[NAME]`.
4. Keep only leaders with at least 2 usable quotes and write `data/leaders.json`.

## Contract 2: clean -> game (`data/leaders.json`)

A list of playable leaders. The game needs nothing else. `data/leaders.sample.json`
has 6 records in exactly this format, so the game can be built before `clean.py` is done.

```json
{
  "id": "Q195725",
  "name": "William Ruto",
  "role": "head of state",
  "country": "Kenya",
  "country_code": "KE",
  "country_code3": "KEN",
  "continent": "Africa",
  "image": "img/Q195725.jpg",
  "image_license": "CC BY 4.0",
  "image_artist": "Presidenza della Repubblica",
  "image_page": "https://commons.wikimedia.org/wiki/File:...",
  "quotes": ["[COUNTRY] will not be left behind.", "There is only a resolution through dialogue."],
  "quotes_original": ["Kenya will not be left behind.", "There is only a resolution through dialogue."]
}
```

Rules:
- every leader in the file is playable: current, photo exists on disk, at least 2 quotes;
- `quotes` and `quotes_original` have the same length and order;
- `image` is relative to `data/`;
- the map answer is `country_code3`.

## Contract 3: game -> stats (`data/results.csv`)

One row per round: `name, country, guessed_country, continent, correct`.
The file is in `.gitignore` (it is produced by playing, it is not source data).

## Run

```
pip install -r requirements.txt
python clean.py
streamlit run app.py
```

`python download.py` is only needed to refresh the data. The downloaded snapshot is committed
in `data/`, so the game runs offline.
