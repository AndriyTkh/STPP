"""Game logic for Politician Guesser. No Streamlit here, so it can be tested.

A game is a few rounds. In each round the player sees a leader's photo and
two quotes with the country hidden, then types the country. The closer the
guessed country is to the right one, the more points (like GeoGuessr).
"""

import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
MAX_POINTS = 5000
SCALE_KM = 2000          # points shrink by e (~2.7x) every 2000 km
EARTH_RADIUS_KM = 6371
RESULT_FIELDS = ["name", "country", "guessed_country", "continent", "correct"]


@dataclass
class Country:
    code3: str
    name: str
    lat: float
    lon: float
    continent: str


@dataclass
class RoundResult:
    name: str
    country: str
    guessed_country: str
    continent: str
    correct: bool
    distance_km: float
    points: int


# ---------- loading data ----------

def load_leaders(data_dir=DATA_DIR):
    """Read the cleaned leaders, or the 6-leader sample if cleaning is not done yet."""
    data_dir = Path(data_dir)
    path = data_dir / "leaders.json"
    if not path.exists():
        path = data_dir / "leaders.sample.json"
    with open(path, encoding="utf-8") as f:
        leaders = json.load(f)
    return [
        leader for leader in leaders
        if len(leader.get("quotes", [])) >= 2
        and len(leader["quotes"]) == len(leader.get("quotes_original", []))
    ]


def load_countries(data_dir=DATA_DIR):
    """All countries the player can type, keyed by ISO alpha-3 code."""
    with open(Path(data_dir) / "countries.json", encoding="utf-8") as f:
        return {row["code3"]: Country(**row) for row in json.load(f)}


def image_path(leader, data_dir=DATA_DIR):
    """Full path of the leader's photo, or None if the file is missing."""
    path = Path(data_dir) / leader.get("image", "")
    return path if path.is_file() else None


# ---------- one game ----------

def pick_leaders(leaders, n=5, rng=random):
    """Choose n different leaders for one game (fewer if there are not enough)."""
    return rng.sample(leaders, min(n, len(leaders)))


def pick_quote_indices(leader, k=2, rng=random):
    """Choose which quotes to show. Indices keep masked and original quotes in step."""
    count = len(leader["quotes"])
    return sorted(rng.sample(range(count), min(k, count)))


# ---------- scoring ----------

def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two points on the Earth's surface."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def score(distance_km):
    """5000 points for 0 km, falling smoothly with distance (GeoGuessr-style)."""
    return round(MAX_POINTS * math.exp(-distance_km / SCALE_KM))


def evaluate_guess(leader, guess_code3, countries):
    """Compare the player's country with the right one and build the round result."""
    answer_code3 = leader["country_code3"]
    guessed = countries.get(guess_code3)
    answer = countries.get(answer_code3)
    correct = guess_code3 == answer_code3

    if correct:
        distance = 0.0
    elif guessed and answer:
        distance = haversine_km(guessed.lat, guessed.lon, answer.lat, answer.lon)
    else:
        distance = float("nan")  # no coordinates: we can't measure, so no points

    points = MAX_POINTS if correct else (0 if math.isnan(distance) else score(distance))
    return RoundResult(
        name=leader["name"],
        country=leader["country"],
        guessed_country=guessed.name if guessed else guess_code3,
        continent=leader["continent"],
        correct=correct,
        distance_km=distance,
        points=points,
    )


# ---------- results ----------

def append_result(result, path=DATA_DIR / "results.csv"):
    """Add one row to results.csv (the file the statistics block reads)."""
    path = Path(path)
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({field: getattr(result, field) for field in RESULT_FIELDS})


def continent_accuracy(results):
    """Accuracy and points per continent for the final screen."""
    df = pd.DataFrame([vars(r) for r in results])
    table = df.groupby("continent").agg(
        rounds=("correct", "size"),
        correct=("correct", "sum"),
        points=("points", "sum"),
    )
    table["accuracy"] = (table["correct"] / table["rounds"] * 100).round().astype(int)
    return table.sort_values("accuracy", ascending=False).reset_index()
