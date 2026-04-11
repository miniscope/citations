"""Fetch BibTeX from CrossRef via DOI content negotiation."""

import sys
from pathlib import Path

import requests

# Add scripts/ to path so we can import bib_utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bibtexparser
from bib_utils import generate_key, make_parser


def fetch_bibtex(doi):
    """Fetch BibTeX for a DOI via CrossRef content negotiation.

    Returns the raw BibTeX string, or None on failure.
    The BibTeX is fetched directly from CrossRef -- never LLM-generated.
    """
    url = f"https://doi.org/{doi}"
    headers = {"Accept": "application/x-bibtex"}

    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            return None
        return resp.text
    except (requests.RequestException, ConnectionError):
        return None


def validate_bibtex(bibtex_str):
    """Check if a string is valid BibTeX by attempting to parse it.

    Returns True if valid, False otherwise.
    """
    if not bibtex_str or not bibtex_str.strip():
        return False
    try:
        parser = make_parser()
        db = bibtexparser.loads(bibtex_str, parser=parser)
        return len(db.entries) > 0
    except Exception:
        return False


def normalize_bibtex_key(bibtex_str):
    """Rewrite the citation key in a BibTeX string to the normalized format.

    Uses the same generate_key() logic as normalize_keys.py.
    Returns the BibTeX string with the key replaced.
    """
    parser = make_parser()
    db = bibtexparser.loads(bibtex_str, parser=parser)
    if not db.entries:
        return bibtex_str

    entry = db.entries[0]
    new_key = generate_key(entry)
    entry["ID"] = new_key

    writer = bibtexparser.bwriter.BibTexWriter()
    writer.indent = "  "
    return bibtexparser.dumps(db, writer=writer)
