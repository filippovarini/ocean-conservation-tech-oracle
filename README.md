# Ocean-Tech Catalog — Phase 1 POC

An automated pipeline that discovers technologies useful for **ocean
conservation** and builds a structured catalog. Phase 1 ingests recent academic
works from [OpenAlex](https://openalex.org), uses one LLM call per item to decide
"is this a usable tool, and is it ocean-relevant?" and to extract structured
attributes, deduplicates against what's already stored, and writes to SQLite.

This is a deliberately small proof of concept. The richer Postgres + pgvector
design from planning is the migration target, not this — see **Deferred to
Phase 2** below for everything intentionally left out.

## Pipeline

```
OpenAlex  ->  pre-filter  ->  gate + extract (LLM)  ->  dedup  ->  SQLite
 (free,      (loose regex,    (Haiku, one call,        (identifier  (catalog.db)
  no key)     skips obvious    forced tool call for     -> fuzzy
              non-tool text)   valid JSON)              name -> new)
```

- **Pre-filter** is loose on purpose: it only drops works with zero tool/method
  signal, to avoid paying for an LLM call on obvious noise. The LLM gate is the
  real precision arbiter.
- **Gate + extract** is a single Haiku call. It returns `is_technology` and
  `ocean_relevant` flags plus the structured fields; we keep the fields only
  when both flags are true.
- **Dedup waterfall**: strong identifier (GitHub repo / homepage) → fuzzy name
  match → otherwise create a new technology. No embeddings yet.
- **`seen_work`** records every fetched item (kept or rejected) so a re-run
  never re-processes — or re-pays the LLM for — the same source item.

## Files

| File          | Role                                                          |
|---------------|---------------------------------------------------------------|
| `taxonomy.py` | Controlled vocabulary (the facets). Edit to grow the taxonomy.|
| `sources.py`  | OpenAlex connector. Add more sources here later.              |
| `llm.py`      | The single gate+extract LLM call (Anthropic).                 |
| `db.py`       | SQLite schema + dedup/write helpers.                          |
| `ingest.py`   | Orchestrator + `list` viewer (CLI entry point).               |

## Setup

```bash
cd marine-technology-inventory
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade        # this box has no system pip
pip install -r requirements.txt

# create your .env (git-ignored) from the template and add your key
cp .env.example .env
# then edit .env:  ANTHROPIC_API_KEY=sk-ant-...
```

The pipeline loads `.env` automatically (via `python-dotenv`), so no `export`
is needed. Any environment variable already set still takes precedence.

## Usage

```bash
# fetch the last 7 days of works (max 25), classify, and store
python ingest.py run

# tune the window / volume / search
python ingest.py run --days 14 --limit 50 --query "coral reef monitoring"

# view the catalog
python ingest.py list
```

A run prints a summary: how many works were fetched, skipped (already seen),
pre-filtered, rejected by the gate, attached to existing tech, or created new.

## Design notes

- **Facets** are stored as JSON arrays in text columns, not normalized junction
  tables — adequate at POC scale and queryable via `json_each()`.
- **Vocabulary is the source of truth**: the LLM prompt is built from
  `taxonomy.py`, so adding a key there makes the extractor start using it on the
  next run. Values the model invents outside the vocab are demoted to
  `free_tags` (a signal that a term may be worth promoting).
- **Cost control** is `seen_work` + the loose pre-filter. Without them a daily
  cron would re-classify the whole lookback window every morning.

---

## Deferred to Phase 2 (intentionally out of scope)

What this POC does **not** do yet, and why each was left out:

- **LLM choice not yet decided.** We hard-code Haiku 4.5 for the gate+extract
  call to get something running. Before scaling, deliberately choose the
  model(s): evaluate accuracy vs. cost on a labelled sample, and consider
  splitting into a *cheap gate* + *stronger extractor* once volume justifies it.
- **No Postgres / pgvector.** SQLite only. No semantic (embedding-based) dedup
  or intent search ("I have BRUVS footage and no time") — dedup is identifier +
  fuzzy name only, which will miss some duplicates.
- **One source only.** OpenAlex. arXiv, bioRxiv, Crossref, GitHub, Zenodo,
  Hugging Face, and Bluesky are all planned but not built. X/Twitter and
  LinkedIn remain out (cost / ToS).
- **WildLabs inventory not ingested.** Pending them sharing the dataset; it will
  enter as another evidence source + identifier type, no schema change needed.
- **No full-text fetch.** We classify on title + abstract only. Fetching the
  paper body / repo README before extraction is the biggest recall win to add,
  since many tools are only named in the body.
- **No human review queue.** Extracted records are written straight to the
  catalog as `candidate`. A review/approval step (and a `published` gate before
  anything reaches a feed) is needed before this is trustworthy.
- **No scoring or digest/newsletter.** Novelty × relevance × credibility ranking
  and the weekly digest are not built.
- **No frontend.** Viewing is the `ingest.py list` CLI only.
- **No scheduling.** Run manually; cron/automation comes once precision is tuned.
- **Minimal error handling.** Single-shot HTTP, no retries/backoff, no rate-limit
  handling, no structured logging.
