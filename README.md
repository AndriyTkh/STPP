# Politician Guesser

A geography game built on open data. You see the photo of a current head of state or
government and two of their quotes, with the country's name hidden. Then you click the
country they lead on a world map.

Team STPP, CS201 "Python: Open Data" hackathon, KSE, 16 November 2026.

## Run

```
pip install -r requirements.txt
python clean.py
streamlit run app.py
```

The downloaded data is committed in `data/`, so the game works offline.
`python download.py` refreshes it from the sources (about 340 requests, several minutes).

## Open data

| Source | Licence | Used for |
|---|---|---|
| [Wikidata](https://www.wikidata.org/) | CC0 | current heads of state and government, countries, ISO codes |
| [Wikimedia Commons](https://commons.wikimedia.org/) | per photo, stored with each leader | portraits |
| [English Wikiquote](https://en.wikiquote.org/) | CC BY-SA 4.0 | quotes |
| [CIA World Leaders](https://www.opensanctions.org/datasets/us_cia_world_leaders/) via OpenSanctions | CIA data is US public domain | check that a leader is still in office |

Queries, retrieval date and selection rules: [data/SOURCES.md](data/SOURCES.md).

## How it works

```
download.py  ->  data/raw/ + data/img/  ->  clean.py  ->  data/leaders.json  ->  game.py + app.py
```

| File | What it does |
|---|---|
| `download.py` | downloads leaders, photos, quote pages and the CIA list |
| `clean.py` | keeps confirmed leaders, extracts quotes, hides country words |
| `game.py` | game logic: rounds, answers, score |
| `app.py` | Streamlit interface with the world map |
| `stats.py` | charts with pandas and matplotlib |

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Team and roles: [docs/TEAM.md](docs/TEAM.md).

## Team

- Andriy Tkhorenko: data download
- Maxim: data cleaning
- Ivan Sidun: game logic and interface
- Ivan Perebynis: statistics and presentation
