"""Block 2: turn the raw downloads in data/raw/ into the game data.

Reads   data/raw/leaders_raw.json, data/raw/wikiquote.json, data/raw/cia_world_leaders.csv
Writes  data/leaders.json

Run:  python clean.py
"""

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"

# letters that do not split into "base letter + accent" in Unicode
SPECIAL_LETTERS = str.maketrans({"ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L"})
# how similar two surnames must be to count as one name in two spellings
SURNAME_SIMILARITY = 0.8


# ---------------------------------------------------------------- loading

def load_leaders() -> pd.DataFrame:
    """Leaders from Wikidata, one row per leader."""
    with open(RAW_DIR / "leaders_raw.json", encoding="utf-8") as file:
        return pd.DataFrame(json.load(file))


def load_cia() -> pd.DataFrame:
    """CIA World Leaders list: one row per (person, country code)."""
    cia = pd.read_csv(RAW_DIR / "cia_world_leaders.csv", dtype=str, keep_default_na=False)
    cia = cia[["name", "countries"]]
    # a few people are listed for several countries: "us;pr" -> two rows
    cia = cia.assign(country_code=cia["countries"].str.upper().str.split(";"))
    return cia.explode("country_code")[["name", "country_code"]]


# ---------------------------------------------------------------- step 1: CIA check

def normalize(text: str) -> str:
    """Lower case without accents: 'Sánchez' -> 'sanchez', 'Tô Lâm' -> 'to lam'."""
    decomposed = unicodedata.normalize("NFKD", text.translate(SPECIAL_LETTERS))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def name_words(name: str) -> set[str]:
    """Words of a name, normalized: 'Kim Jong-un' -> {'kim', 'jong', 'un'}."""
    return set(re.findall(r"[a-z]+", normalize(name)))


def cia_surnames(cia_name: str) -> set[str]:
    """The CIA writes surnames in capitals: 'Pham Minh CHINH' -> {'chinh'}."""
    words = re.findall(r"[^\W\d_]+", cia_name)
    capital_words = [word for word in words if word.isupper() and len(word) > 1]
    if not capital_words:  # a few entries have no capitals: 'Janez Jansa'
        capital_words = words[-1:]
    return name_words(" ".join(capital_words))


def same_surname(first: str, second: str) -> bool:
    """True for one surname in two transliterations: 'sharaa' / 'shara'."""
    return SequenceMatcher(None, first, second).ratio() >= SURNAME_SIMILARITY


def is_confirmed(leader_name: str, known_surnames: set[str]) -> bool:
    """Does the leader's name match a surname the CIA lists for the country?"""
    words = name_words(leader_name)
    if words & known_surnames:
        return True
    last_word = re.findall(r"[a-z]+", normalize(leader_name))[-1]
    return any(same_surname(last_word, surname) for surname in known_surnames)


def filter_confirmed(leaders: pd.DataFrame, cia: pd.DataFrame) -> pd.DataFrame:
    """Keep leaders whose surname is on the CIA list for the same country.

    This removes stale Wikidata entries (people who already left office).
    Countries the CIA does not cover at all (its own, the United States)
    cannot be checked, so their leaders are kept.
    """
    cia = cia.assign(surnames=cia["name"].map(cia_surnames))
    # country code -> all surnames the CIA lists for that country
    surnames_by_country = cia.groupby("country_code")["surnames"].agg(lambda sets: set().union(*sets))

    def keep(leader: pd.Series) -> bool:
        if leader["country_code"] not in surnames_by_country:
            return True
        return is_confirmed(leader["name"], surnames_by_country[leader["country_code"]])

    return leaders[leaders.apply(keep, axis=1)].reset_index(drop=True)


# ---------------------------------------------------------------- main

def main() -> None:
    leaders = load_leaders()
    print(f"raw leaders:       {len(leaders)}")

    leaders = filter_confirmed(leaders, load_cia())
    print(f"confirmed by CIA:  {len(leaders)}")


if __name__ == "__main__":
    main()
