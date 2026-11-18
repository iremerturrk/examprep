# ExamPrep

A personal, local exam-preparation tool for university courses. You feed it the
course material — **lecture slides, homework sheets and past exams (PDF)** — and
it builds a map of learning objectives, then generates **multiple-choice
objective tests** with matching **flashcards** (in-app and as Anki decks).

Questions are not copied from past exams: every past question is abstracted into
a *question pattern* (skill + angle + variation axes), and new questions are
generated from new combinations. Answers to algorithmic questions are
**computed in Python**, not trusted from the language model.

> UI languages: **Türkçe · Deutsch · English** (sidebar selector, remembered in the URL as `?lang=`).

## How it works

```
PDFs ──ingest──▶ pages (text + image) ──/ders-analiz──▶ topics · objectives · patterns · past questions
                                                         │
                         /kazanim-testi ◀────────────────┘
                               │
             test (35 MC questions) + flashcards ──▶ Streamlit: cards → test → submit → results
```

There is **no LLM API** in the code. All analysis and generation is done by
[Claude Code](https://claude.com/claude-code) skills in `.claude/skills/`; the
Python package only does deterministic work (storage, validation, verification,
similarity, scoring) and exposes it through a JSON CLI. Streamlit is just the UI.

| Layer | What it does |
|---|---|
| Claude Code skills | read PDFs (incl. scanned pages), extract objectives and patterns, write questions and cards, act as an independent difficulty/quality judge |
| Python CLI (`python -m examprep`) | ingest, database read/write (JSON in, Pydantic-validated), answer verification, similarity check, test composition, Anki export |
| Streamlit (`app.py`) | courses, PDF upload, objective-map review & approval, tests and results |

## Features

- **Ingest** – PDF text and page images (PyMuPDF); scanned pages are detected and read from the image by the skill.
- **Objective map** – topic tree, objectives with Bloom level, question patterns, linked past questions, difficulty profile; reviewable and approvable in the UI. Past questions that have no matching slides yet become *past-question objectives* instead of being dropped.
- **Objective tests** – 35 questions by default:
  - *Part 1 · Basics* (20): definitions, basic properties, tiny examples, spread over as many objectives as possible
  - *Part 2 · Intermediate* (10): application and analysis
  - *Part 3 · Exam level* (5): each parallel to a specific past exam question
  - 4 options (A–D), exactly one correct, distractors based on typical mistakes; objective names are hidden during the test
- **Cumulative scheduling** – no fixed weekly plan: each new test draws from everything uploaded so far, prioritising untested objectives, spaced review of older ones and objectives you answered wrongly.
- **Flashcards** – 2–4 cards per measured objective (definition, fact, example, common mistake), reviewed before the test; exportable per test as `.apkg`.
- **Quality gates**
  - verifiers for knapsack (brute force / greedy / DP table), Turing machines, RAM programs, SAT (2-SAT, Horn-SAT, k-SAT → 3-SAT), 3-SAT → SubsetSum, average-case cost and asymptotic ordering (sympy, incl. oscillating functions)
  - copy detection against past questions (multilingual embeddings + data-token overlap, course notation excluded)
  - an independent judge (separate sub-agent) scores difficulty and checks answer key and distractors
- **Results** – score per section, weak objectives with their cards, explanations, perceived-difficulty feedback.

## Requirements

- macOS / Linux, Python **3.12** (managed with [uv](https://github.com/astral-sh/uv))
- [Claude Code](https://claude.com/claude-code) for the analysis and generation skills
- ~1 GB disk for `sentence-transformers` / PyTorch and the small multilingual embedding model (downloaded once, then offline)

## Setup

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
.venv/bin/pytest            # optional: run the test suite
.venv/bin/streamlit run app.py
```

The app listens on **localhost only** (`.streamlit/config.toml`). All data —
database, page images, exports — lives in `data/`, which is git-ignored.

## Usage

1. **Create a course and upload PDFs** in the UI (*Courses*, *Upload PDFs*) or via CLI:
   ```bash
   .venv/bin/python -m examprep course add --name "Info 3"
   .venv/bin/python -m examprep ingest slides/01-Knapsack.pdf --course 1 --type slides
   ```
2. **Analyse the course** in Claude Code: `/ders-analiz 1`. Re-run it whenever you upload new material; records you approved are never overwritten.
3. **Review the objective map** in the UI and approve what looks right.
4. **Generate a test**: `/kazanim-testi 1` (section sizes are adjustable, e.g. `--temel 20 --orta 10 --sinav 5`).
5. **Study and take the test** on the *Tests* page: cards → test → submit → results. Download the Anki deck from the cards tab.
6. Optional: `/web-kesif 1` adds question patterns inspired by other universities' public exercise sheets and past exams (abstracted, never copied; the source URL is stored).

## CLI overview

All commands print JSON; errors go to stderr as `{"error", "details"}` with exit code 1.

| Group | Commands |
|---|---|
| `course` | `add`, `list`, `map`, `check` |
| `ingest`, `doc` | `ingest <pdf>`, `doc list`, `doc pages` |
| `topic`, `objective`, `question`, `archetype` | batch `import --json` (with `--dry-run`), `question list`, `archetype merge` |
| `profile` | `compute` |
| `test` | `compose`, `show`, `list`, `finalize`, `discard` |
| `gen` | `import` (generated questions), `judge` |
| `verify`, `similarity` | `verify run`, `verify list`, `similarity check` |
| `card` | `import`, `list`, `reject`, `export` |
| `submission` | `submit`, `show` |

Run `.venv/bin/python -m examprep --help` (or `<group> --help`) for details.

## Project layout

```
app.py                  Streamlit entry point (navigation, language selector)
pages/                  Courses, Upload, Objective map, Tests
examprep/
  models.py             SQLAlchemy data model
  db.py                 engine, sessions, lightweight SQLite migration
  ingest/               PDF → pages
  analysis.py           objective map import/upsert, weights, profile, coverage
  testgen.py            test composition, quality gates, finalisation
  verify/               answer verifiers
  similarity.py         copy detection
  cards.py              flashcards and Anki export
  submissions.py        grading and results
  i18n.py               UI strings (tr / de / en)
  cli.py                JSON CLI
.claude/skills/         ders-analiz, kazanim-testi, web-kesif
tests/                  pytest suite
```

## Notes

- Single user, runs locally; no authentication.
- Generated content follows the course: questions and card fronts in the exam language (German), explanations and card backs in Turkish. The UI language selector translates the interface only.
- `CLAUDE.md` contains the design principles the skills follow.
