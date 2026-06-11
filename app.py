"""Flask review UI for the ocean-tech catalog.

A small server-rendered frontend over the same catalog.db the pipeline writes:

  GET  /                     list technologies, filter by review status
  GET  /tech/<id>            detail view: full facets + evidence
  POST /tech/<id>/review     set status (approve / reject / reset to pending)

Review state reuses the existing `technology.status` column:
  candidate = pending review (schema default) | approved | rejected

Run:  python app.py            (then open http://127.0.0.1:5000)
"""

import json
from urllib.parse import urlparse

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db
import taxonomy

app = Flask(__name__)
app.secret_key = "ocean-tech-review-poc"  # only used for flash messages

# Map the review action posted by a button to a stored status.
ACTIONS = {"approve": db.APPROVED, "reject": db.REJECTED, "reset": db.PENDING}

# Human-readable labels for the status values.
STATUS_LABELS = {db.PENDING: "Pending", db.APPROVED: "Approved", db.REJECTED: "Rejected"}

# Pretty labels for facet vocab keys, e.g. "optical_imagery" -> "Optical imagery".
_FACET_LABEL = lambda v: v.replace("_", " ").capitalize()

# Readable label for an evidence source_type, e.g. "openalex" -> "OpenAlex".
SOURCE_LABELS = {"openalex": "OpenAlex"}


def _row_to_tech(row):
    """sqlite Row -> dict with JSON facet columns parsed into lists."""
    t = dict(row)
    for facet in ("modalities", "functions", "habitats", "taxa", "free_tags"):
        t[facet] = json.loads(t.get(facet) or "[]")
    return t


@app.template_filter("facet")
def facet_filter(value):
    return _FACET_LABEL(value)


@app.template_filter("source")
def source_filter(value):
    return SOURCE_LABELS.get(value, (value or "").replace("_", " ").title())


@app.template_filter("host")
def host_filter(url):
    """Bare hostname of a URL, e.g. 'https://doi.org/10.x' -> 'doi.org'.

    Lets a source link advertise what kind of resource it points to
    (doi.org, github.com, a journal site) without showing the full URL.
    """
    if not url:
        return ""
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


@app.context_processor
def inject_globals():
    return {"STATUS_LABELS": STATUS_LABELS}


@app.route("/")
def index():
    status = request.args.get("status") or "all"
    if status not in (*db.REVIEW_STATES, "all"):
        status = "all"
    conn = db.connect()
    db.init(conn)
    rows = db.list_technologies(conn, None if status == "all" else status)
    counts = db.status_counts(conn)
    techs = [_row_to_tech(r) for r in rows]
    conn.close()
    return render_template("index.html", techs=techs, counts=counts, active=status)


@app.route("/tech/<int:tech_id>")
def detail(tech_id):
    conn = db.connect()
    db.init(conn)
    row = db.get_technology(conn, tech_id)
    if row is None:
        conn.close()
        abort(404)
    tech = _row_to_tech(row)
    evidence = [dict(e) for e in db.get_evidence(conn, tech_id)]
    conn.close()
    return render_template("detail.html", tech=tech, evidence=evidence)


@app.route("/tech/<int:tech_id>/review", methods=["POST"])
def review(tech_id):
    action = request.form.get("action")
    if action not in ACTIONS:
        abort(400, "unknown review action")
    conn = db.connect()
    db.init(conn)
    if db.get_technology(conn, tech_id) is None:
        conn.close()
        abort(404)
    db.set_status(conn, tech_id, ACTIONS[action])
    conn.close()
    flash(f"#{tech_id} marked {STATUS_LABELS[ACTIONS[action]].lower()}.")
    # Return to wherever the action was triggered (list or detail).
    return redirect(request.form.get("next") or url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
