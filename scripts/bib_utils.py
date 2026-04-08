#!/usr/bin/env python3
"""Shared utilities for BibTeX processing scripts."""

import json
import subprocess
import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


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
