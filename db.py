"""SQLite storage for the ocean-tech catalog.

Four tables, deliberately small for a POC:

  technology            - one canonical row per real-world tool/method
  technology_identifier - strong dedup keys (github repo, homepage)
  evidence              - provenance: one row per paper/post that mentions a tech
  seen_work             - every fetched work, so we never re-process (or re-pay
                          the LLM) for the same source item twice

Facets are stored as JSON arrays in text columns rather than normalized
junction tables — fine at POC scale, and easy to query with json_each() if
needed. The Postgres+pgvector design from planning is the migration target,
not this.
"""

import json
import sqlite3
from difflib import SequenceMatcher

DEFAULT_DB = "catalog.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS technology (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    name_norm     TEXT NOT NULL,          -- lowercased, for fuzzy matching
    description   TEXT,
    homepage_url  TEXT,
    modalities    TEXT DEFAULT '[]',      -- JSON arrays of vocab keys
    functions     TEXT DEFAULT '[]',
    habitats      TEXT DEFAULT '[]',
    taxa          TEXT DEFAULT '[]',
    maturity      TEXT,
    openness      TEXT,
    free_tags     TEXT DEFAULT '[]',
    status        TEXT DEFAULT 'candidate',  -- candidate | published
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS technology_identifier (
    id            INTEGER PRIMARY KEY,
    technology_id INTEGER NOT NULL REFERENCES technology(id),
    id_type       TEXT NOT NULL,          -- 'github' | 'homepage'
    id_value      TEXT NOT NULL,
    UNIQUE (id_type, id_value)
);

CREATE TABLE IF NOT EXISTS evidence (
    id              INTEGER PRIMARY KEY,
    technology_id   INTEGER NOT NULL REFERENCES technology(id),
    source_type     TEXT NOT NULL,        -- 'openalex'
    external_id     TEXT NOT NULL,        -- e.g. openalex work id
    url             TEXT,
    doi             TEXT,
    title           TEXT,
    snippet         TEXT,
    published_date  TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS seen_work (
    source_type   TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    is_candidate  INTEGER NOT NULL,       -- 0 = rejected by filter/gate, 1 = became evidence
    technology_id INTEGER,                -- set when is_candidate = 1
    seen_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (source_type, external_id)
);
"""

NAME_MATCH_THRESHOLD = 0.88  # fuzzy name similarity for auto-attach


def connect(path=DEFAULT_DB):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    conn.commit()


# --- seen-work bookkeeping (cost control) ----------------------------------

def already_seen(conn, source_type, external_id):
    row = conn.execute(
        "SELECT 1 FROM seen_work WHERE source_type=? AND external_id=?",
        (source_type, external_id),
    ).fetchone()
    return row is not None


def mark_seen(conn, source_type, external_id, is_candidate, technology_id=None):
    conn.execute(
        "INSERT OR REPLACE INTO seen_work "
        "(source_type, external_id, is_candidate, technology_id) VALUES (?,?,?,?)",
        (source_type, external_id, 1 if is_candidate else 0, technology_id),
    )


# --- dedup waterfall: identifier -> fuzzy name -> new ----------------------

def _normalize(name):
    return " ".join(name.lower().split())


def find_by_identifier(conn, identifiers):
    """identifiers: list of (id_type, id_value). Returns technology_id or None."""
    for id_type, id_value in identifiers:
        row = conn.execute(
            "SELECT technology_id FROM technology_identifier WHERE id_type=? AND id_value=?",
            (id_type, id_value),
        ).fetchone()
        if row:
            return row["technology_id"]
    return None


def find_by_name(conn, name):
    """Best fuzzy match above threshold. Returns (technology_id, score) or (None, best)."""
    target = _normalize(name)
    best_id, best_score = None, 0.0
    for row in conn.execute("SELECT id, name_norm FROM technology"):
        score = SequenceMatcher(None, target, row["name_norm"]).ratio()
        if score > best_score:
            best_id, best_score = row["id"], score
    if best_score >= NAME_MATCH_THRESHOLD:
        return best_id, best_score
    return None, best_score


# --- writes ----------------------------------------------------------------

def create_technology(conn, fields):
    cur = conn.execute(
        """INSERT INTO technology
           (name, name_norm, description, homepage_url,
            modalities, functions, habitats, taxa, maturity, openness, free_tags)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            fields["name"],
            _normalize(fields["name"]),
            fields.get("description"),
            fields.get("homepage_url"),
            json.dumps(fields.get("modalities", [])),
            json.dumps(fields.get("functions", [])),
            json.dumps(fields.get("habitats", [])),
            json.dumps(fields.get("taxa", [])),
            fields.get("maturity"),
            fields.get("openness"),
            json.dumps(fields.get("free_tags", [])),
        ),
    )
    return cur.lastrowid


def add_identifiers(conn, technology_id, identifiers):
    for id_type, id_value in identifiers:
        conn.execute(
            "INSERT OR IGNORE INTO technology_identifier "
            "(technology_id, id_type, id_value) VALUES (?,?,?)",
            (technology_id, id_type, id_value),
        )


def add_evidence(conn, technology_id, ev):
    conn.execute(
        """INSERT INTO evidence
           (technology_id, source_type, external_id, url, doi, title, snippet, published_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            technology_id,
            ev["source_type"],
            ev["external_id"],
            ev.get("url"),
            ev.get("doi"),
            ev.get("title"),
            ev.get("snippet"),
            ev.get("published_date"),
        ),
    )
    conn.execute(
        "UPDATE technology SET updated_at=datetime('now') WHERE id=?", (technology_id,)
    )
