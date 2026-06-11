"""Source connectors. Phase 1 ships one: OpenAlex.

OpenAlex is free, needs no API key, returns structured metadata + abstracts,
and indexes the journals where new marine methods actually get described. Add
more sources later by writing another fetch_*() that yields the same dict shape.
"""

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta

OPENALEX_URL = "https://api.openalex.org/works"

# A broad-ish default query. The LLM gate is the precision arbiter, so we err
# toward recall here. Tune the search string rather than the gate.
DEFAULT_QUERY = (
    "marine OR ocean OR reef OR underwater OR coral OR deep sea OR marine protected area OR mpa "
    "AND (monitoring OR detection OR bioacoustics OR eDNA OR "
    '"remote sensing" OR survey OR identification OR technology)'
)

# polite-pool contact; OpenAlex asks for a mailto, not a key
MAILTO = "fppvrn@gmail.com"


def _reconstruct_abstract(inverted_index):
    """OpenAlex returns abstracts as an inverted index {word: [positions]}."""
    if not inverted_index:
        return ""
    positions = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def fetch_openalex(query=DEFAULT_QUERY, days=7, limit=25):
    """Yield recent works as dicts: external_id, doi, url, title, abstract, published_date."""
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {
        "filter": f"from_publication_date:{since},title_and_abstract.search:{query}",
        "sort": "publication_date:desc",
        "per-page": min(limit, 200),
        "mailto": MAILTO,
    }
    url = f"{OPENALEX_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"ocean-tech-catalog ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    for w in data.get("results", [])[:limit]:
        loc = w.get("primary_location") or {}
        yield {
            "source_type": "openalex",
            "external_id": w.get("id", ""),          # e.g. https://openalex.org/W123
            "doi": w.get("doi"),
            "url": loc.get("landing_page_url") or w.get("id"),
            "title": w.get("display_name") or "",
            "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
            "published_date": w.get("publication_date"),
        }
