# CLAUDE.md

Guidance for working in this repo. User-facing docs live in `README.md`; this
file is the internal map.

## What this is

A POC pipeline + review UI that discovers ocean-conservation technologies from
research sources, tags them against a controlled vocabulary using an LLM, and
stores them in SQLite for human review. Target user: marine-protected-area
teams who are time-poor and not tech-savvy — keep that audience in mind for any
user-facing copy.

## Environment

- Python, virtualenv at `.venv`. **This box has no system pip** — bootstrap with
  `python -m ensurepip --upgrade` inside the venv if needed.
- Run things with `.venv/bin/python ...` (don't assume the venv is activated).
- Secrets load from a git-ignored `.env` via `python-dotenv`; needs
  `ANTHROPIC_API_KEY`. No `export` required.

## Commands

```bash
.venv/bin/python ingest.py run                 # fetch + classify + store (last 7 days)
.venv/bin/python ingest.py run --days 14 --limit 50 --query "..."
.venv/bin/python ingest.py list                # print the catalog (CLI)
.venv/bin/python app.py                         # Flask review UI on 127.0.0.1:5000
```

There is no test suite. To smoke-test the web app, use Flask's `test_client()`
(see how it was done in commit history) rather than relying on a running server
— port 5000 may already be held by a stale instance.

## Layout

| File           | Role |
|----------------|------|
| `ingest.py`    | Pipeline CLI: fetch → pre-filter → LLM gate+extract → dedup → store. |
| `sources.py`   | Source connectors. Only OpenAlex today; each yields a common dict shape. |
| `llm.py`       | The single LLM call (gate + extract) via a forced tool call. |
| `taxonomy.py`  | Controlled vocabulary. **Source of truth** for the facets. |
| `db.py`        | SQLite schema, dedup helpers, and the read/write helpers the UI uses. |
| `app.py`       | Flask review UI (list / detail / approve-reject). |
| `templates/`   | Server-rendered Jinja templates + inline CSS in `base.html`. |
| `catalog.db`   | The SQLite store. Pipeline and UI share it — no separate review DB. |

## Model / LLM

- Uses the Anthropic Python SDK (`anthropic`). Model is pinned in `llm.py`
  (`MODEL`), currently Haiku 4.5. It forces a `tool_use` call (`record_technology`)
  so the response is guaranteed-valid structured JSON — parse `block.input`.
- The extraction prompt is **built from `taxonomy.py`** at call time. To add or
  change a facet value, edit the lists in `taxonomy.py`; the extractor picks it
  up on the next run. No prompt editing needed.

## Data model (in `db.py`)

Four tables, deliberately small:

- `technology` — one canonical row per real tool. Facets (`modalities`,
  `functions`, `habitats`, `taxa`, `free_tags`) are stored as **JSON arrays in
  text columns**, not normalized tables. Parse them before use (see
  `_row_to_tech` in `app.py`).
- `technology_identifier` — strong dedup keys (github repo, homepage).
- `evidence` — one row per source paper/dataset that mentions a tech. This is
  the "original resource" surfaced in the UI as **Sources**.
- `seen_work` — every fetched item, so we never re-process (or re-pay the LLM)
  for the same source twice. Note: this also means **re-running `ingest` will not
  refresh existing evidence rows** — a backfill is needed to update them.

**Review status reuses `technology.status`**: `candidate` (default = pending) →
`approved` / `rejected`. Constants and helpers are in `db.py` (`PENDING`,
`APPROVED`, `REJECTED`, `set_status`, `status_counts`).

**Dedup waterfall** (`ingest.run`): match by identifier → fuzzy name (threshold
`db.NAME_MATCH_THRESHOLD`) → otherwise create new.

## Conventions / gotchas

- Facet vocab keys are snake_case (`optical_imagery`); the UI prettifies them via
  the `facet` Jinja filter. Don't hand-format labels in templates.
- `sources._best_url` chooses the most *accessible* link per work (open-access /
  publisher / repo page) over a bare `doi.org` resolver — keep that bias when
  touching source connectors; the audience is practitioners, not researchers.
- Cost control rests on `seen_work` + the loose regex pre-filter in `ingest.py`.
  Don't remove them — without them a daily run re-classifies the whole window.
- Keep the POC simple. Postgres/pgvector, semantic dedup, multi-source ingest,
  scoring, and a public frontend are intentionally deferred (see README history).
