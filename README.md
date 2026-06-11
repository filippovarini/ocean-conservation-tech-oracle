# Ocean-Tech Catalog

A tool that automatically discovers technologies useful for **ocean**  
**conservation** and organizes them into a searchable, reviewable catalog.

## What you can do with it

- **Build a catalog** of ocean conservation technologies from recent research.
- **Browse and search** them by what they do, their maturity, and openness.
- **Review** each entry — approve the useful ones, reject the rest — in a simple
web interface.
- **Trace every entry** back to its original source (paper, dataset, or
repository), with links chosen to be as accessible as possible.

## Setup

You'll need an [Anthropic API key](https://console.anthropic.com/) (used to
classify and tag each technology).

```bash
cd marine-technology-inventory
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade        # only if this machine has no pip
pip install -r requirements.txt

# create your .env from the template and add your key
cp .env.example .env
# then edit .env:  ANTHROPIC_API_KEY=sk-ant-...
```

Your key is loaded automatically — no `export` needed.

## Building the catalog

```bash
# discover technologies from the last 7 days of research
python ingest.py run

# widen the window, pull more, or focus the search
python ingest.py run --days 14 --limit 50 --query "coral reef monitoring"

# list what's in the catalog from the command line
python ingest.py list
```

Each run prints a short summary of how many technologies it found and added.
You can run it as often as you like — it remembers what it has already seen, so
re-running won't create duplicates.

## Reviewing in the browser

A built-in web app lets you browse the catalog and approve or reject each
technology.

```bash
python app.py          # then open http://127.0.0.1:5000
```

- **List view** — filter by status (All / Pending / Approved / Rejected),
see each technology's tags at a glance, and approve or reject without leaving
the page. Each card links straight to its original source.
- **Detail view** — the full description and tags, the technology's website if
it has one, and every **Source** (papers, datasets, and references it was
found in) with direct links.

New technologies start as **Pending**. Approve the ones worth keeping; reject
the rest. The catalog and the review app share the same data, so you can review
while a run is in progress.

## Sources to Include

- [x] **OpenAlex** for scientific papers
- [ ] GitHub for software
- [ ] BlueSky for posts
- [ ] OCTO Newsletter
- [ ] Other newsletters (to find)

## Tips

- Start with a broad run to populate the catalog, then narrow `--query` to focus
on a topic you care about (e.g. `"eDNA"`, `"bioacoustics"`, `"MPA enforcement"`).
- If a page won't load at `http://localhost:5000`, try `http://127.0.0.1:5000`
directly (some networks block `localhost`).

