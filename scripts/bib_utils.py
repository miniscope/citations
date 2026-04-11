#!/usr/bin/env python3
"""Shared utilities for BibTeX processing scripts."""

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

STOP_WORDS = {"a", "an", "the", "of", "and", "in", "for", "on", "to", "with", "by", "is", "are"}


def load_config():
    """Load config.json and return (repo_root, config)."""
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    return repo_root, config


def make_parser():
    """Create a configured BibTexParser."""
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    return parser


def load_bib_entries(bib_paths):
    """Parse .bib files from disk into a dict keyed by entry ID."""
    parser = make_parser()
    entries = {}
    for path in bib_paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            db = bibtexparser.load(f, parser=parser)
        for entry in db.entries:
            entries[entry["ID"]] = entry
    return entries


def load_base_entries(bib_files, base_ref):
    """Load entries from a git ref for comparison. Returns dict keyed by ID."""
    parser = make_parser()
    entries = {}
    for bib_file in bib_files:
        try:
            result = subprocess.run(
                ["git", "show", f"{base_ref}:{bib_file}"],
                capture_output=True, text=True, check=True,
            )
            db = bibtexparser.loads(result.stdout, parser=parser)
            for entry in db.entries:
                entries[entry["ID"]] = entry
        except subprocess.CalledProcessError:
            print(f"  Warning: could not read {bib_file} at {base_ref}", file=sys.stderr)
        except (bibtexparser.bibdatabase.UndefinedString, KeyError) as e:
            print(f"  Warning: could not parse {bib_file} at {base_ref}: {e}", file=sys.stderr)
    return entries


def entry_changed(old, new):
    """Check if any fields differ between two entries (ignoring key and type)."""
    all_fields = set(old.keys()) | set(new.keys())
    all_fields -= {"ID", "ENTRYTYPE"}
    for field in all_fields:
        if old.get(field, "").strip() != new.get(field, "").strip():
            return True
    return False


def clean_latex(value):
    """Strip common LaTeX artifacts from a string."""
    if not isinstance(value, str):
        return str(value)
    return value.replace("{", "").replace("}", "").strip()


def build_template_call(name, params):
    """Build a wikitext template invocation from a name and dict of params."""
    lines = ["{{" + name]
    for key, value in params.items():
        if value:
            lines.append(f"|{key}={value}")
    lines.append("}}")
    return "\n".join(lines)


# --- Functions extracted from normalize_keys.py and check_duplicates.py ---


def slugify(text):
    """Convert text to a clean slug: lowercase, underscores, ascii only."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    text = text.strip("_")
    return text


def get_first_author_lastname(author_str):
    """Extract first author's last name from a BibTeX author string."""
    first_author = clean_latex(re.split(r"\s+and\s+", author_str)[0])

    if "," in first_author:
        return first_author.split(",")[0].strip()
    else:
        parts = first_author.split()
        return parts[-1] if parts else "unknown"


def get_first_title_word(title):
    """Extract the first significant word from a title (skipping stop words)."""
    title = clean_latex(title)
    words = re.sub(r"[^\w\s]", "", title).split()
    for word in words:
        if word.lower() not in STOP_WORDS:
            return word.lower()
    return words[0].lower() if words else "untitled"


def generate_key(entry):
    """Generate a normalized citation key from entry metadata."""
    author = get_first_author_lastname(entry.get("author", "unknown"))
    year = entry.get("year", "0000")
    title_word = get_first_title_word(entry.get("title", "untitled"))
    return slugify(f"{author} {year} {title_word}")


def normalize_title(title):
    """Normalize a title for comparison: lowercase, strip punctuation/whitespace."""
    title = clean_latex(title)
    title = re.sub(r"[^\w\s]", "", title)
    return " ".join(title.lower().split())
