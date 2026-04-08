#!/usr/bin/env python3
"""Check for duplicate BibTeX entries based on metadata similarity.

Compares entries by DOI (exact match) and by title+year (fuzzy match).
Exits with code 1 and prints warnings if duplicates are found.
"""

import re
import sys

from bib_utils import clean_latex, load_bib_entries, load_config


def normalize_title(title):
    """Normalize a title for comparison: lowercase, strip punctuation/whitespace."""
    title = clean_latex(title)
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
    repo_root, config = load_config()

    bib_paths = [repo_root / p for p in config["bib_files"]]
    all_entries = list(load_bib_entries(bib_paths).values())

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
