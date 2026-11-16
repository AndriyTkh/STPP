# Team STPP: who does what

Project: **Politician Guesser** (CS201 hackathon, 16 Nov 2026, Group 1).
Data flow and file formats: [ARCHITECTURE.md](ARCHITECTURE.md). Hackathon rules: [RULES.md](RULES.md).

## Roles

| Person | Block | Own files (nobody else edits them) | Branch |
|---|---|---|---|
| Andriy Tkhorenko | 1. Download | `download.py`, `data/raw/`, `data/img/`, `data/SOURCES.md`, `docs/` | `feat/download` |
| Maxim | 2. Cleaning | `clean.py`, `data/leaders.json`, `tests/test_clean.py` | `feat/clean` |
| Ivan Sidun | 3. Game | `game.py`, `app.py`, `requirements.txt`, `tests/test_game.py` | `feat/game` |
| Ivan Perebynis | 4. Presentation | `stats.py`, `charts/`, `docs/DEMO.md`, slides | `feat/presentation` |

What each block delivers:

1. **Download (Andriy).** A script that pulls leaders, photos, quote pages and the CIA list from the open sources, and the downloaded snapshot committed in `data/`.
2. **Cleaning (Maxim).** `clean.py` reads `data/raw/`, keeps confirmed current leaders, extracts quotes, hides country words, writes `data/leaders.json`. Uses pandas.
3. **Game (Ivan Sidun).** `game.py` holds the logic (pick a leader, pick 2 quotes, check the clicked country, keep score, log the round). `app.py` is the Streamlit screen: photo + 2 quotes, then the world map.
4. **Presentation (Ivan Perebynis).** `stats.py` draws charts with pandas + matplotlib (leaders per continent, share with quotes, accuracy from `data/results.csv`). Demo script for 2 minutes and the slides. Runs the demo.

## Working in parallel

- Blocks talk only through files in `data/`. The formats are fixed in ARCHITECTURE.md. If you need a format change, say so in the chat first.
- Ivan Sidun does not wait for Maxim: build the game on `data/leaders.sample.json`, then switch the file name to `data/leaders.json`.
- Ivan Perebynis does not wait for the game: the dataset charts need only `data/raw/leaders_raw.json`.

## Git rules

- Everyone commits **from their own GitHub account**. The Git point is for commits by different members.
- One branch per person, one pull request per block into `main`. Another team member approves it.
- Few commits: commit when a piece works, not after every edit. 1-3 commits per person is right.
- Edit only your own files. That is what keeps merges free of conflicts.
- No secrets, no personal data in the repo.

## Deadlines (today)

| Time | What |
|---|---|
| 18:30 | Raw data and docs are in `main`. Everyone pulls |
| 19:15 | `clean.py` writes `data/leaders.json` |
| 19:30 | Game works end to end on the sample file |
| 19:45 | Game runs on the real `leaders.json`. Charts ready |
| 20:00 | Last merge into `main`. After that only rehearsal |
| **20:15** | **Repo freezes. A commit after 20:15 costs 5 points** |
| 20:15-21:00 | Defence online, Group 1, Google Meet. Demo of 2 minutes or less |

Anyone on the team can be asked to explain the code, so read the other blocks once before the defence.
