"""Streamlit interface for Politician Guesser, styled as an old newspaper.

Stages of one round:  front (photo + quotes) -> card (type the country) -> reveal.
After the last round: final (score and accuracy per continent).
Run: streamlit run app.py
"""

import base64
import html
import random
import re
from functools import partial
from datetime import date
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

import game

ROUNDS = 5
CSS_PATH = Path(__file__).parent / "assets" / "newspaper.css"
GOOD, CLOSE = 5000, 2500   # points thresholds for the green / yellow verdict

st.set_page_config(page_title="Politician Guesser", page_icon="📰", layout="centered")


# ---------- data (loaded once, then cached) ----------

@st.cache_data
def load_data():
    return game.load_leaders(), game.load_countries()


@st.cache_data
def photo_data_uri(path):
    """Embed a local photo into HTML as base64, so it can sit inside our own markup."""
    mime = "image/png" if str(path).endswith(".png") else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


# ---------- game state ----------

def start_game():
    leaders, _ = load_data()
    st.session_state.leaders = game.pick_leaders(leaders, ROUNDS)
    st.session_state.round = 0
    st.session_state.results = []
    st.session_state.stage = "front"
    st.session_state.quote_idx = game.pick_quote_indices(st.session_state.leaders[0])


def current_leader():
    return st.session_state.leaders[st.session_state.round]


def go_to(stage):
    st.session_state.stage = stage


def submit_guess(countries):
    guess = st.session_state.guess
    result = game.evaluate_guess(current_leader(), guess, countries)
    game.append_result(result)
    st.session_state.results.append(result)
    st.session_state.last_guess = guess
    st.session_state.stage = "reveal"


def next_round():
    st.session_state.round += 1
    st.session_state.guess = None
    if st.session_state.round >= len(st.session_state.leaders):
        st.session_state.stage = "final"
    else:
        st.session_state.quote_idx = game.pick_quote_indices(current_leader())
        st.session_state.stage = "front"


def total_points():
    return sum(r.points for r in st.session_state.results)


# ---------- small HTML helpers ----------

def show(markup):
    st.markdown(markup, unsafe_allow_html=True)


def masked(quote):
    """Escape the quote and draw [COUNTRY]-style tokens as black censor bars."""
    return re.sub(r"\[([A-Z]+)\]", r'<span class="mask">\1</span>', html.escape(quote))


def torn_polygon(seed, teeth=34, depth=4.0):
    """CSS clip-path with ragged top and bottom edges, like a strip torn from a page."""
    rng = random.Random(seed)
    top = [f"{i * 100 / teeth:.1f}% {rng.uniform(0, depth):.1f}%" for i in range(teeth + 1)]
    bottom = [f"{100 - i * 100 / teeth:.1f}% {100 - rng.uniform(0, depth):.1f}%" for i in range(teeth + 1)]
    return "polygon(" + ", ".join(top + bottom) + ")"


def photo_html(leader):
    path = game.image_path(leader)
    img = f'<img src="{photo_data_uri(str(path))}" alt="portrait">' if path else "<p><i>Photo unavailable</i></p>"
    credit = html.escape(f'{leader.get("image_artist", "")} · {leader.get("image_license", "")}')
    return (f'<div class="photo-frame">{img}</div>'
            f'<div class="caption">Photo: <a href="{html.escape(leader.get("image_page", ""))}" target="_blank">'
            f'{credit}</a>, Wikimedia Commons</div>')


def masthead():
    show(f"""
    <div class="masthead">
      <div class="mast-row">
        <div class="ear left">Round<b>{min(st.session_state.round + 1, len(st.session_state.leaders))}/{len(st.session_state.leaders)}</b></div>
        <h1 class="paper-title">The Politician Guesser</h1>
        <div class="ear right">Score<b>{total_points():,}</b></div>
      </div>
      <div class="dateline">
        <span>Vol. CS201 · No. {min(st.session_state.round + 1, len(st.session_state.leaders))}</span>
        <span>{date.today():%A, %B %d, %Y}</span>
        <span>Open data edition · Price: one guess</span>
      </div>
    </div>""")


# ---------- screens ----------

def front_page(leader):
    quotes = [leader["quotes"][i] for i in st.session_state.quote_idx]
    show('<div class="headline boxed">Who said this?</div>'
         '<div class="subhead">A sitting world leader speaks. The country has been censored by our editors.</div>')
    left, right = st.columns([5, 6], gap="large")
    with left:
        show(photo_html(leader))
    with right:
        for n, quote in enumerate(quotes, 1):
            show(f'<span class="quote-label">Statement {n}</span><div class="quote">{masked(quote)}</div>')
    st.button("Turn the page →", on_click=go_to, args=("card",), width="stretch")


def card_page(leader, countries):
    show('<div class="headline">Name the country</div>'
         '<div class="subhead">The closer your guess, the more points. Exact country: 5,000.</div>')
    with st.container(key="card"):
        left, right = st.columns([2, 5], gap="medium")
        with left:
            show(photo_html(leader))
        with right:
            show(f'<p class="card-name">{html.escape(leader["name"])}</p>'
                 f'<span class="card-role">{html.escape(leader["role"])}</span>')
            for i in st.session_state.quote_idx:
                show(f'<div class="card-quote">“{masked(leader["quotes"][i])}”</div>')
        codes = sorted(countries, key=lambda c: countries[c].name)
        guess = st.session_state.get("guess")
        show('<span class="quote-label">Click the country on the map</span>')
        st.plotly_chart(pick_map(codes, guess), key="pick_map", on_select=partial(on_map_pick, codes),
                        selection_mode="points", width="stretch", theme=None,
                        config={"displayModeBar": False, "scrollZoom": True})
        st.selectbox("…or type it (handy for tiny states):", codes, key="guess",
                     index=None, format_func=lambda c: countries[c].name, placeholder="e.g. Monaco")
        label = f"Submit guess: {countries[guess].name}" if guess else "Pick a country first"
        st.button(label, on_click=submit_guess, args=(countries,), disabled=guess is None, width="stretch")


def on_map_pick(codes):
    """A click on the map selects one country: copy it into the guess."""
    points = st.session_state.pick_map.selection.point_indices
    if points:
        st.session_state.guess = codes[points[0]]


def style_geo(fig, height):
    """Old-paper look shared by both maps."""
    fig.update_geos(projection_type="natural earth", showframe=False, showcoastlines=False,
                    showland=True, landcolor="#e6d9b8", showocean=True, oceancolor="#d6e2e4",
                    showcountries=True, countrycolor="#b3a585", bgcolor="rgba(0,0,0,0)",
                    lataxis_range=[-58, 85], lonaxis_range=[-180, 180])
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, dragmode=False)
    return fig


def pick_map(codes, guess):
    """Clickable world map: every country is one point; the picked one turns pink."""
    countries = load_data()[1]
    fig = go.Figure(go.Choropleth(
        locations=codes, z=[1 if c == guess else 0 for c in codes],
        text=[countries[c].name for c in codes], hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, "#efe3c4"], [1, "#e08f7c"]], zmin=0, zmax=1, showscale=False,
        marker_line_color="#a89a80", marker_line_width=0.6,
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
    ))
    return style_geo(fig, 420)


def verdict(result):
    if result.correct:
        return "good", "Correct!"
    if result.points >= CLOSE:
        return "close", "Close call"
    return "far", "Missed"


def reveal_page(leader, countries):
    result = st.session_state.results[-1]
    tone, stamp = verdict(result)
    if result.correct:
        detail = f"You named it. +{result.points:,} points"
    else:
        detail = (f"You said {html.escape(result.guessed_country)}, "
                  f"{result.distance_km:,.0f} km away. +{result.points:,} points")
    show(f"""
    <div class="torn-wrap"><div class="torn {tone}" style="clip-path: {torn_polygon(st.session_state.round)}">
      <div class="kicker">Extra! Extra! {html.escape(leader["name"])} leads</div>
      <div class="answer">{html.escape(leader["country"])}</div>
      <div class="detail">{detail}</div>
      <div class="stamp {tone}">{stamp}</div>
    </div></div>""")
    st.plotly_chart(answer_map(st.session_state.last_guess, leader["country_code3"], countries),
                    width="stretch", theme=None, config={"displayModeBar": False, "scrollZoom": False})
    show('<span class="quote-label">The uncensored quotes</span>')
    for i in st.session_state.quote_idx:
        show(f'<div class="card-quote">“{html.escape(leader["quotes_original"][i])}”</div>')
    last = st.session_state.round + 1 >= len(st.session_state.leaders)
    st.button("See the final edition →" if last else "Next round →", on_click=next_round, width="stretch")


def answer_map(guess_code, answer_code, countries):
    """World map: the right country in green, the guess in pink, a dashed line between them."""
    fig = go.Figure()
    fig.add_trace(go.Choropleth(locations=[answer_code, guess_code], z=[1, 0], showscale=False,
                                colorscale=[[0, "#e8b4a6"], [1, "#8fb07f"]], marker_line_color="#3a312b",
                                hoverinfo="skip"))
    guess, answer = countries.get(guess_code), countries.get(answer_code)
    if guess and answer and guess_code != answer_code:
        fig.add_trace(go.Scattergeo(lat=[guess.lat, answer.lat], lon=[guess.lon, answer.lon], mode="lines+markers",
                                    line=dict(color="#2b2420", width=2, dash="dash"),
                                    marker=dict(size=9, color=["#c0604c", "#4f7a45"]), hoverinfo="skip"))
    return style_geo(fig, 330)


def final_page():
    results = st.session_state.results
    best = game.MAX_POINTS * len(results)
    show(f"""
    <div class="headline boxed">Final edition</div>
    <div class="subhead">{sum(r.correct for r in results)} of {len(results)} leaders placed correctly</div>
    <div class="big-score">{total_points():,} <span style="font-size:1.4rem">/ {best:,}</span></div>
    <hr><span class="quote-label">Accuracy by continent</span>""")
    table = game.continent_accuracy(results)
    colors = ["#b5c9a7", "#b4cbe0", "#f2dc9d", "#e8b4a6"]
    rows = "".join(
        f'<div class="bar-row"><span>{html.escape(row.continent)}</span>'
        f'<div class="bar"><span style="width:{row.accuracy}%;background:{colors[i % len(colors)]}"></span></div>'
        f'<span>{row.accuracy}%</span></div>'
        for i, row in enumerate(table.itertuples()))
    show(rows)
    show('<hr><span class="quote-label">The round-up</span>')
    for r in results:
        mark = "✔" if r.correct else "✘"
        show(f'<div class="card-quote">{mark} <b>{html.escape(r.name)}</b>: {html.escape(r.country)}. '
             f'You said {html.escape(r.guessed_country)} · {r.points:,} pts</div>')
    st.button("Print a new edition (play again)", on_click=start_game, width="stretch")


# ---------- main ----------

def main():
    st.html(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>")
    leaders, countries = load_data()
    if not leaders:
        st.error("No playable leaders found in data/.")
        st.stop()
    if "stage" not in st.session_state:
        start_game()

    masthead()
    stage = st.session_state.stage
    if stage == "final":
        final_page()
        return
    leader = current_leader()
    if stage == "front":
        front_page(leader)
    elif stage == "card":
        card_page(leader, countries)
    else:
        reveal_page(leader, countries)


main()
