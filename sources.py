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


def _best_url(w):
    """Pick the most accessible landing page for a work.

    Tuned for practitioners, not researchers: prefer an open-access landing
    page (free full text), then a real journal/publisher/repository page, and
    only fall back to the bare doi.org resolver or the OpenAlex record when
    nothing friendlier exists. OpenAlex returns the abstract-bearing work
    object by default, so best_oa_location / primary_location / locations are
    all present.
    """
    # Priority order of where to look for a landing page.
    candidates = []
    for loc in (w.get("best_oa_location"), w.get("primary_location")):
        candidates.append((loc or {}).get("landing_page_url"))
    for loc in w.get("locations") or []:
        candidates.append((loc or {}).get("landing_page_url"))

    # First pass: a "clean" page that isn't just a DOI/OpenAlex redirect.
    for url in candidates:
        if url and "doi.org" not in url and "openalex.org" not in url:
            return url
    # Otherwise the best landing page we have, then DOI, then the record id.
    for url in candidates:
        if url:
            return url
    return w.get("doi") or w.get("id")


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
        yield {
            "source_type": "openalex",
            "external_id": w.get("id", ""),          # e.g. https://openalex.org/W123
            "doi": w.get("doi"),
            "url": _best_url(w),
            "title": w.get("display_name") or "",
            "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
            "published_date": w.get("publication_date"),
        }
