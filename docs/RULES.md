# CS201 Hackathon: Python Open Data. Rules

Date: 2026-11-16. Sources: the instructor's slides ("Хакатон з Python Open Data.pdf", 8 slides), `hackathon_criteria.pdf` and the instructor's Slack messages in #cs201. The opening was not recorded, so the slides stand in for it.

## Timeline

| Time | What |
|---|---|
| 16:30 – 20:15 | Work on the project (work from anywhere) |
| **20:15** | **Repo freezes. Any commit after 20:15 = −5 points** |
| 20:15 – 21:00 | Defence, online, each group in its own Google Meet (link sent separately) |

We are **Group 1** (7 teams: NoC, bed trip, DataVolt, segfault goes brrrrr, STPP, MAGA, Слуга Вайбкода).
Per team: 3 min demo + 2 min questions + 1 min buffer = 6 min.

## Mandatory (otherwise 0 points)

1. **Python is the main language.** All core logic (data processing, calculations, how the program runs) is in Python. Other languages only as helpers, e.g. HTML/CSS for styling.
2. **Open data.** The data comes from an open source, and the project is built on it.

## Disqualification (0 for the whole hackathon)

- The mandatory requirements are not met.
- Before the start, the repo held code or anything other than the `data` folder.
- The team did not register by 14 November. (We registered.)

## Scoring (15 points)

| Criterion | What is judged | Points |
|---|---|---|
| Working program | Starts and does what we claim during the demo, with no errors | 0–6 |
| Python code quality | Readable and structured (functions, clear names), proper use of Python and its libraries | 0–4 |
| Idea and usefulness | How interesting and original the idea is, how useful the result | 0–3 |
| Team work in Git | Commits during the hackathon made by different team members | 0–1 |
| Demo | Fit into the time limit and clearly showed what was done | 0–1 |

The most important thing is that **the program actually works in the demo**.

How points are given:
- **Working program:** 6 = everything stable and the features are finished. 4–5 = the core works, with small glitches or something unfinished. 2–3 = only partly works, or the demo has errors. 1 = starts but does almost nothing. 0 = does not start.
- **Code quality:** 4 = clean code split into functions or modules, with libraries used where they fit (pandas, matplotlib, etc.). 3 = well organised, with small flaws. 2 = understandable overall, but with repetition or long unbroken blocks of code. 1 = hard to read.
- **Idea:** 3 = an original idea with a useful or interesting result. 2 = a good but fairly standard idea. 1 = a simple idea with little in the result.

## Penalties and other rules

- **−5:** a commit after 20:15.
- **−1:** the demo runs well over the limit. The sources disagree on the limit: the slides say 3 min, while the criteria PDF and the last slide say 1–2 min. **We aim for 2 minutes or less.**
- **AI use is allowed** and does not lower the grade. But **any team member** may be asked to explain how the code works, so everyone must understand it.
- The `data` folder may hold csv, json and similar files that the program uses (instructor, Slack 11-14).
- Room: 16:30 start in S01 (Slack 11-14) or 2.08 (thread note 16:36). Online participation is allowed.

## Our team rules

- Working app first. A simple, reliable demo beats features.
- Git flow: one branch per feature, a pull request into `main`, a teammate reviews it, and **every member commits from their own account** before 20:15.
- Last merge at 20:00. Then only a demo rehearsal, no more commits.
- Name the open-data source (with a link) in the README.
- No secrets in the repo.
