"""Phase 1 pipeline: fetch -> pre-filter -> gate+extract -> dedup -> store.

Usage:
    python ingest.py run [--days 7] [--limit 25] [--query "..."] [--db catalog.db]
    python ingest.py list [--db catalog.db]          # view the catalog
"""

import argparse
import json
import re
import sys

import db
import llm
import sources
import taxonomy

# Loose lexical pre-filter: skip works with no tool/method signal before
# spending an LLM call. Deliberately permissive — the gate is the real arbiter.
_TECH_SIGNAL = re.compile(
    r"\b(detect|monitor|sensor|acoustic|hydrophone|edna|imagery|camera|video|"
    r"sonar|drone|satellite|telemetr|algorithm|model|network|software|platform|"
    r"tool|system|device|pipeline|dataset|classifier|tag|tracking)\w*",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)", re.IGNORECASE)


def _passes_prefilter(text):
    return bool(_TECH_SIGNAL.search(text or ""))


def _extract_identifiers(extracted, abstract):
    """Strong dedup keys from the extracted tech + abstract: github repo, homepage."""
    ids = []
    blob = f"{extracted.get('homepage_url', '')} {abstract}"
    for m in _GITHUB_RE.finditer(blob):
        ids.append(("github", m.group(1).lower().rstrip("/").removesuffix(".git")))
    home = (extracted.get("homepage_url") or "").strip()
    if home and "github.com" not in home.lower():
        ids.append(("homepage", home.lower().rstrip("/")))
    return ids


def _clean_facets(extracted):
    """Keep only valid vocab values; demote unknown multi-facet values to free_tags."""
    free = list(extracted.get("free_tags") or [])
    for name, vocab in taxonomy.MULTI_FACETS.items():
        valid, unknown = [], []
        for v in extracted.get(name) or []:
            (valid if v in vocab else unknown).append(v)
        extracted[name] = valid
        free.extend(unknown)
    for name, vocab in taxonomy.SINGLE_FACETS.items():
        if extracted.get(name) not in vocab:
            extracted[name] = None
    extracted["free_tags"] = sorted(set(free))
    return extracted


def run(args):
    conn = db.connect(args.db)
    db.init(conn)

    stats = {"fetched": 0, "skipped_seen": 0, "prefiltered": 0,
             "rejected": 0, "attached": 0, "created": 0}

    for work in sources.fetch_openalex(query=args.query, days=args.days, limit=args.limit):
        stats["fetched"] += 1
        src, ext = work["source_type"], work["external_id"]

        if db.already_seen(conn, src, ext):
            stats["skipped_seen"] += 1
            continue

        text = f"{work['title']} {work['abstract']}"
        if not _passes_prefilter(text):
            db.mark_seen(conn, src, ext, is_candidate=False)
            stats["prefiltered"] += 1
            continue

        extracted = llm.gate_and_extract(work["title"], work["abstract"])
        if not extracted or not (extracted.get("is_technology") and extracted.get("ocean_relevant")):
            db.mark_seen(conn, src, ext, is_candidate=False)
            stats["rejected"] += 1
            continue

        extracted = _clean_facets(extracted)
        identifiers = _extract_identifiers(extracted, work["abstract"])

        # dedup waterfall: identifier -> fuzzy name -> new
        tech_id = db.find_by_identifier(conn, identifiers)
        if tech_id is None:
            tech_id, _ = db.find_by_name(conn, extracted["name"])
        if tech_id is None:
            tech_id = db.create_technology(conn, extracted)
            stats["created"] += 1
        else:
            stats["attached"] += 1

        db.add_identifiers(conn, tech_id, identifiers)
        db.add_evidence(conn, tech_id, {
            "source_type": src,
            "external_id": ext,
            "url": work["url"],
            "doi": work["doi"],
            "title": work["title"],
            "snippet": work["abstract"][:500],
            "published_date": work["published_date"],
        })
        db.mark_seen(conn, src, ext, is_candidate=True, technology_id=tech_id)
        conn.commit()

    conn.commit()
    print("Run complete:")
    for k, v in stats.items():
        print(f"  {k:14} {v}")


def list_catalog(args):
    conn = db.connect(args.db)
    db.init(conn)
    rows = conn.execute(
        """SELECT t.*, COUNT(e.id) AS n_evidence
           FROM technology t LEFT JOIN evidence e ON e.technology_id = t.id
           GROUP BY t.id ORDER BY t.updated_at DESC"""
    ).fetchall()
    if not rows:
        print("Catalog is empty. Run:  python ingest.py run")
        return
    print(f"{len(rows)} technologies in catalog:\n")
    for r in rows:
        mods = ", ".join(json.loads(r["modalities"])) or "-"
        funcs = ", ".join(json.loads(r["functions"])) or "-"
        print(f"#{r['id']}  {r['name']}  [{r['maturity'] or '?'}/{r['openness'] or '?'}]")
        print(f"     {(r['description'] or '').strip()}")
        print(f"     modalities: {mods}")
        print(f"     functions:  {funcs}")
        print(f"     evidence: {r['n_evidence']}   {r['homepage_url'] or ''}")
        print()


def main():
    p = argparse.ArgumentParser(description="Ocean-tech catalog Phase 1 pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="fetch + classify + store new technologies")
    pr.add_argument("--days", type=int, default=7, help="lookback window")
    pr.add_argument("--limit", type=int, default=25, help="max works to fetch")
    pr.add_argument("--query", default=sources.DEFAULT_QUERY, help="OpenAlex search string")
    pr.add_argument("--db", default=db.DEFAULT_DB)
    pr.set_defaults(func=run)

    pl = sub.add_parser("list", help="print the catalog")
    pl.add_argument("--db", default=db.DEFAULT_DB)
    pl.set_defaults(func=list_catalog)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
