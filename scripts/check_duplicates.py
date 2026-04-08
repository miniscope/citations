#!/usr/bin/env python3
"""Check for duplicate BibTeX entries based on metadata similarity.

Compares entries by DOI (exact match) and by title+year (fuzzy match).
Exits with code 1 and prints warnings if duplicates are found.
"""

import json
import re
import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


def normalize_title(title):
    """Normalize a title for comparison: lowercase, strip punctuation/whitespace."""
    title = title.replace("{", "").replace("}", "")
    title = re.sub(r"[^\w\s]", "", title)
    return " ".join(title.lower().split())


def check_duplicates(entries):
    """Check for duplicate entries. Returns list of warning strings."""
    warnings = []

    # Exact DOI match
    doi_map = {}
    for entry in entries:
        doi = entry.get("doi", "").strip().lower()
        if not doi:
            continue
        if doi in doi_map:
            warnings.append(
                f"Duplicate DOI ({doi}):\n"
                f"  - {doi_map[doi]['ID']}\n"
                f"  - {entry['ID']}"
            )
        else:
            doi_map[doi] = entry

    # Title + year match
    title_year_map = {}
    for entry in entries:
        title = normalize_title(entry.get("title", ""))
        year = entry.get("year", "")
        if not title:
            continue
        key = (title, year)
        if key in title_year_map:
            other = title_year_map[key]
            if other["ID"] != entry["ID"]:
                warnings.append(
                    f"Same title and year:\n"
                    f"  - {other['ID']}: {entry.get('title', '')}\n"
                    f"  - {entry['ID']}: {entry.get('title', '')}"
                )
        else:
            title_year_map[key] = entry

    return warnings


def main():
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode

    all_entries = []
    for bib_file in config["bib_files"]:
        path = repo_root / bib_file
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            db = bibtexparser.load(f, parser=parser)
        all_entries.extend(db.entries)

    warnings = check_duplicates(all_entries)

    if warnings:
        print(f"Found {len(warnings)} potential duplicate(s):\n")
        for w in warnings:
            print(f"  ⚠ {w}\n")
        sys.exit(1)
    else:
        print(f"No duplicates found across {len(all_entries)} entries.")


if __name__ == "__main__":
    main()
