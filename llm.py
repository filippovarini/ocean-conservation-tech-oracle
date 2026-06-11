"""The one LLM station in the pipeline: gate + extract in a single call.

At POC volume there's no value in a cheap-gate-then-strong-extract split, so
we do both at once with Haiku and force a tool call for guaranteed-valid JSON.
The model decides is_technology + ocean_relevant AND fills the structured
fields; ingest.py only keeps the fields when both flags are true.

Phase 2 (see README): pick the right model deliberately, and consider the
two-stage cheap-gate / strong-extract split once volume justifies it.
"""

import os

import anthropic
from dotenv import load_dotenv

import taxonomy

load_dotenv()  # read ANTHROPIC_API_KEY (and friends) from a local .env file

MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client():
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment.")
        _client = anthropic.Anthropic()
    return _client


TOOL = {
    "name": "record_technology",
    "description": (
        "Record whether a source text describes a concrete tool, method, "
        "device, software, or platform that a marine-protected-area team could "
        "USE for ocean conservation, and if so its structured attributes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_technology": {
                "type": "boolean",
                "description": "True if the text describes a usable tool/method/device/platform, "
                "not merely a study that happens to use one.",
            },
            "ocean_relevant": {
                "type": "boolean",
                "description": "True if it is applicable to marine/ocean conservation "
                "(including land-origin tools clearly transferable to marine work).",
            },
            "name": {"type": "string", "description": "Canonical name of the technology."},
            "description": {
                "type": "string",
                "description": "One or two sentences: what it is and what it does.",
            },
            "homepage_url": {
                "type": "string",
                "description": "Project/product/repo URL if stated in the text, else empty.",
            },
            "modalities": {"type": "array", "items": {"type": "string", "enum": taxonomy.MODALITIES}},
            "functions": {"type": "array", "items": {"type": "string", "enum": taxonomy.FUNCTIONS}},
            "habitats": {"type": "array", "items": {"type": "string", "enum": taxonomy.HABITATS}},
            "taxa": {"type": "array", "items": {"type": "string", "enum": taxonomy.TAXA}},
            "maturity": {"type": "string", "enum": taxonomy.MATURITY},
            "openness": {"type": "string", "enum": taxonomy.OPENNESS},
            "free_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Salient keywords not covered by the controlled facets.",
            },
        },
        "required": ["is_technology", "ocean_relevant", "name", "description"],
    },
}

PROMPT = """You are curating a catalog of technologies useful for ocean conservation,
aimed at marine-protected-area teams who are time-poor and not tech-savvy.

Decide if the text below describes a TOOL a team could use (a device, software,
model, platform, method, or product) — not just a study that used one. Then judge
ocean relevance. If both are true, fill the structured fields using only the
controlled vocabulary; put anything salient outside the vocab into free_tags.

Controlled vocabulary:
{vocab}

--- SOURCE ---
Title: {title}
Abstract: {abstract}
"""


def gate_and_extract(title, abstract):
    """Return the tool-call dict, or None on an unexpected (non-tool) response."""
    client = _get_client()
    prompt = PROMPT.format(vocab=taxonomy.vocab_prompt_block(), title=title, abstract=abstract)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "record_technology"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return block.input
    return None
