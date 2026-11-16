import csv
import random

import game
from game import Country

COUNTRIES = {
    "UKR": Country("UKR", "Ukraine", 49.0, 32.0, "Europe"),
    "POL": Country("POL", "Poland", 52.0, 19.0, "Europe"),
    "KEN": Country("KEN", "Kenya", 0.1, 38.0, "Africa"),
}
RUTO = {"name": "William Ruto", "country": "Kenya", "country_code3": "KEN",
        "continent": "Africa", "quotes": ["a", "b", "c"], "quotes_original": ["A", "B", "C"]}


def test_haversine_kyiv_warsaw():
    assert abs(game.haversine_km(50.45, 30.52, 52.23, 21.01) - 690) < 20


def test_score_exact_is_max_and_decreases():
    assert game.score(0) == 5000
    assert game.score(1000) > game.score(3000) > 0


def test_evaluate_guess_correct_and_wrong():
    right = game.evaluate_guess(RUTO, "KEN", COUNTRIES)
    assert right.correct and right.points == 5000 and right.distance_km == 0
    wrong = game.evaluate_guess(RUTO, "UKR", COUNTRIES)
    assert not wrong.correct and 0 < wrong.points < 5000
    assert wrong.guessed_country == "Ukraine"


def test_pick_leaders_caps_at_available():
    picked = game.pick_leaders([{"id": 1}, {"id": 2}, {"id": 3}], n=5, rng=random.Random(0))
    assert len(picked) == 3 and len({p["id"] for p in picked}) == 3


def test_append_result_writes_header_once(tmp_path):
    path = tmp_path / "results.csv"
    result = game.evaluate_guess(RUTO, "POL", COUNTRIES)
    game.append_result(result, path)
    game.append_result(result, path)
    rows = list(csv.reader(open(path)))
    assert rows[0] == game.RESULT_FIELDS and len(rows) == 3


def test_continent_accuracy():
    results = [game.evaluate_guess(RUTO, "KEN", COUNTRIES), game.evaluate_guess(RUTO, "UKR", COUNTRIES)]
    table = game.continent_accuracy(results)
    assert table.loc[0, "continent"] == "Africa" and table.loc[0, "accuracy"] == 50


def test_sample_data_loads():
    leaders = game.load_leaders()
    countries = game.load_countries()
    assert leaders and all(l["country_code3"] in countries for l in leaders)
