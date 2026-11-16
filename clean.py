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

MIN_QUOTE_LENGTH = 40
MAX_QUOTE_LENGTH = 300
MAX_QUOTES_PER_LEADER = 20
# a quote counts as English if it has at least this many of these words
ENGLISH_WORDS = {"the", "and", "of", "to", "is", "in", "that", "we", "it", "are", "for",
                 "not", "be", "this", "will", "have", "with", "our", "you", "a", "i"}
MIN_ENGLISH_WORDS = 3
# level-2 sections of a Wikiquote page that are not the leader's own words
SKIPPED_SECTIONS = re.compile(r"about|misattributed|disputed|external|see also|references", re.IGNORECASE)

MIN_QUOTES_TO_PLAY = 2
# names people really use that Wikidata does not list, by country code
EXTRA_COUNTRY_NAMES = {
    "US": ["America", "United States of America", "US"],
    "GB": ["UK", "U.K.", "Great Britain", "England"],
    "CN": ["PRC"],
    "KP": ["Korea"],
    "NL": ["Holland"],
    "CZ": ["Czechia"],
    "TR": ["Turkiye"],
    "TL": ["East Timor"],
    "CI": ["Cote d'Ivoire"],
}
EXTRA_DEMONYMS = {
    "UA": ["Ukrainian"],
    "KP": ["Korean"],
    "GB": ["English", "Brit"],
}
# columns of data/leaders.json, in the order of the contract with the game
OUTPUT_COLUMNS = ["id", "name", "role", "country", "country_code", "country_code3", "continent",
                  "image", "image_license", "image_artist", "image_page", "quotes", "quotes_original"]


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


def load_wikiquote() -> dict[str, dict]:
    """Raw Wikiquote pages: {leader id: {"title": ..., "wikitext": ...}}."""
    with open(RAW_DIR / "wikiquote.json", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------------- step 1: CIA check

def strip_accents(text: str) -> str:
    """'Sánchez' -> 'Sanchez', 'Tô Lâm' -> 'To Lam'."""
    decomposed = unicodedata.normalize("NFKD", text.translate(SPECIAL_LETTERS))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Lower case without accents: 'Sánchez' -> 'sanchez'."""
    return strip_accents(text).lower()


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


# ---------------------------------------------------------------- step 2: quotes

def own_quote_lines(wikitext: str) -> list[str]:
    """Lines of the page without the sections that hold other people's words.

    'Quotes about ...', 'Misattributed', 'Disputed', 'External links' and so on
    are level-2 sections ('== Title =='); everything under them is skipped.
    """
    lines = []
    skipping = False
    for line in wikitext.splitlines():
        heading = re.match(r"==([^=].*?)==\s*$", line)
        if heading:
            skipping = bool(SKIPPED_SECTIONS.search(heading.group(1)))
        elif not skipping:
            lines.append(line)
    return lines


def strip_markup(text: str) -> str:
    """Wiki markup -> plain text: '[[w:Kenya|Kenya]] is ''home''' -> 'Kenya is home'."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)           # comments
    text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", text, flags=re.DOTALL)  # footnotes
    text = re.sub(r"<[^>]+>", " ", text)                              # other html tags
    text = re.sub(r"\{\{w\|(?:[^{}|]*\|)?([^{}|]*)\}\}", r"\g<1>", text)   # {{w|Page|label}}
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)                        # other templates
    text = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]", r"\g<1>", text)  # [[Page|label]]
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\g<1>", text)        # [url label]
    text = re.sub(r"\[https?://[^\]]*\]", "", text)                    # [url]
    text = re.sub(r"'{2,}", "", text)                                 # bold and italics
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip('"“”').strip()                                  # outer quotation marks


def is_english(text: str) -> bool:
    """Latin letters only and a few very common English words."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters or any(not ch.isascii() for ch in letters):
        return False
    words = re.findall(r"[a-z]+", text.lower())
    return sum(word in ENGLISH_WORDS for word in words) >= MIN_ENGLISH_WORDS


def is_usable_quote(text: str) -> bool:
    """Right length, English, no markup left over."""
    if not MIN_QUOTE_LENGTH <= len(text) <= MAX_QUOTE_LENGTH:
        return False
    if re.search(r"[\[\]{}<>|=]|https?:", text):
        return False
    return is_english(text)


def split_long_quote(quote: str) -> list[str]:
    """Cut a quote that is too long into parts made of whole sentences.

    Sentences are packed together while the part still fits the length limit,
    so a long speech becomes several shorter quotes instead of being lost.
    """
    if len(quote) <= MAX_QUOTE_LENGTH:
        return [quote]
    parts = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", quote):
        if current and len(current) + 1 + len(sentence) > MAX_QUOTE_LENGTH:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    parts.append(current)
    return parts


def extract_quotes(wikitext: str) -> list[str]:
    """Quotes of one Wikiquote page.

    On Wikiquote a quote is a line that starts with one '*'. Lines with '**'
    under it are its source and are skipped, except '** Translation: ...',
    which is the English version of a quote given in another language.
    """
    quotes = []
    for line in own_quote_lines(wikitext):
        translation = re.match(r"\*\*\s*Translation:(.*)", line)
        if translation:
            quote = strip_markup(translation.group(1))
        elif re.match(r"\*[^*:#]", line):
            quote = strip_markup(line[1:])
        else:
            continue
        for part in split_long_quote(quote):
            if is_usable_quote(part) and part not in quotes:
                quotes.append(part)
    return quotes[:MAX_QUOTES_PER_LEADER]


def add_quotes(leaders: pd.DataFrame, wikiquote: dict[str, dict]) -> pd.DataFrame:
    """Add the column 'quotes_original' (a list, empty if the leader has no page)."""
    def quotes_of(leader_id: str) -> list[str]:
        page = wikiquote.get(leader_id)
        return extract_quotes(page["wikitext"]) if page else []

    return leaders.assign(quotes_original=leaders["id"].map(quotes_of))


# ---------------------------------------------------------------- step 3: masking

def country_names(leader: pd.Series) -> list[str]:
    """Every way the country can be named in a quote.

    Adds short forms to the Wikidata names:
    "People's Republic of China" -> 'China', 'The Gambia' -> 'Gambia'.
    """
    names = [leader["country"], *leader["country_aliases"]]
    names += EXTRA_COUNTRY_NAMES.get(leader["country_code"], [])
    short_forms = [re.sub(r"^.* of (the )?|^The ", "", name) for name in names]
    return names + short_forms


def people_names(leader: pd.Series) -> list[str]:
    """Demonyms with their plurals: 'Kenyan' -> 'Kenyan', 'Kenyans'."""
    demonyms = leader["demonyms"] + EXTRA_DEMONYMS.get(leader["country_code"], [])
    return demonyms + [demonym + "s" for demonym in demonyms]


def city_names(leader: pd.Series) -> list[str]:
    """The capital, also without what follows a comma: 'Washington, D.C.' -> 'Washington'."""
    capital = leader["capital"] or ""
    return [capital, capital.split(",")[0]]


def person_names(leader: pd.Series) -> list[str]:
    """The full name and each of its capitalised words, with and without accents.

    'Pedro Sánchez' -> 'Pedro Sánchez', 'Pedro', 'Sánchez', 'Pedro Sanchez', 'Sanchez'.
    Particles ('of', 'bin') and numerals ('II') are not names, so they are left out.
    """
    full_name = leader["name"]
    words = [word for word in re.findall(r"[^\W\d_]+", full_name)
             if len(word) >= 3 and word[0].isupper() and not word.isupper()]
    names = [full_name, *words]
    return names + [strip_accents(name) for name in names]


def words_pattern(words: list[str]) -> re.Pattern | None:
    """One regex that finds any of the words as a whole word.

    Longer words go first, so 'South Africa' wins over 'Africa'.
    Abbreviations ('US', 'UAE') must match the case exactly, otherwise
    the pronoun 'us' would be hidden; everything else ignores case.
    """
    words = sorted({word for word in words if word}, key=len, reverse=True)
    if not words:
        return None
    alternatives = [re.escape(word) if word.isupper() else f"(?i:{re.escape(word)})"
                    for word in words]
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)")


def mask_quote(quote: str, leader: pd.Series) -> str:
    """Hide the words that give the answer away.

    'Kenya will not fail, Kenyans know it' -> '[COUNTRY] will not fail, [PEOPLE] know it'
    People go before the country, so 'South African' is not cut into '[COUNTRY]n'.
    """
    replacements = [
        ("[PEOPLE]", people_names(leader)),
        ("[COUNTRY]", country_names(leader)),
        ("[CITY]", city_names(leader)),
        ("[NAME]", person_names(leader)),
    ]
    for placeholder, words in replacements:
        pattern = words_pattern(words)
        if pattern:
            quote = pattern.sub(placeholder, quote)
    return quote


def add_masked_quotes(leaders: pd.DataFrame) -> pd.DataFrame:
    """Add the column 'quotes': 'quotes_original' with the giveaway words hidden."""
    def masked(leader: pd.Series) -> list[str]:
        return [mask_quote(quote, leader) for quote in leader["quotes_original"]]

    return leaders.assign(quotes=leaders.apply(masked, axis=1))


# ---------------------------------------------------------------- step 4: output

def keep_playable(leaders: pd.DataFrame) -> pd.DataFrame:
    """Leaders the game can show: enough quotes and a photo on disk."""
    enough_quotes = leaders["quotes"].str.len() >= MIN_QUOTES_TO_PLAY
    has_photo = leaders["image"].map(lambda image: (DATA_DIR / image).is_file())
    return leaders[enough_quotes & has_photo].reset_index(drop=True)


def save_leaders(leaders: pd.DataFrame) -> None:
    """Write data/leaders.json in the format the game expects."""
    records = leaders[OUTPUT_COLUMNS].to_dict(orient="records")
    with open(DATA_DIR / "leaders.json", "w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- main

def main() -> None:
    leaders = load_leaders()
    print(f"raw leaders:       {len(leaders)}")

    leaders = filter_confirmed(leaders, load_cia())
    print(f"confirmed by CIA:  {len(leaders)}")

    leaders = add_quotes(leaders, load_wikiquote())
    quote_counts = leaders["quotes_original"].str.len()
    print(f"with any quote:    {(quote_counts > 0).sum()}")
    print(f"with 2+ quotes:    {(quote_counts >= 2).sum()}")

    leaders = keep_playable(add_masked_quotes(leaders))
    save_leaders(leaders)
    print(f"playable leaders:  {len(leaders)}  ->  data/leaders.json")


if __name__ == "__main__":
    main()
