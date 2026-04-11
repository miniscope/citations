#!/usr/bin/env python3
"""Normalize BibTeX citation keys to a consistent format.

Rewrites keys in .bib files to: {first_author_lastname}_{year}_{first_title_word}
All lowercase, spaces replaced with underscores. Duplicates get _a, _b suffixes.

Exits with code 0 if no changes, 1 if keys were rewritten.
"""

import sys

import bibtexparser
from bibtexparser.bwriter import BibTexWriter

from bib_utils import generate_key, load_config, make_parser


def normalize_bib_file(bib_path):
    """Normalize keys in a .bib file. Returns True if any keys changed."""
    parser = make_parser()

    with open(bib_path, encoding="utf-8") as f:
        db = bibtexparser.load(f, parser=parser)

    # Generate new keys and track duplicates
    key_counts = {}
    new_keys = []
    for entry in db.entries:
        base_key = generate_key(entry)
        count = key_counts.get(base_key, 0)
        key_counts[base_key] = count + 1
        new_keys.append((base_key, count))

    # Assign suffixes for duplicates
    changed = False
    for i, entry in enumerate(db.entries):
        base_key, index = new_keys[i]
        if key_counts[base_key] > 1:
            suffix = chr(ord("a") + index)
            final_key = f"{base_key}_{suffix}"
        else:
            final_key = base_key

        if entry["ID"] != final_key:
            print(f"  {entry['ID']} -> {final_key}")
            entry["ID"] = final_key
            changed = True

    if changed:
        writer = BibTexWriter()
        writer.indent = "  "
        with open(bib_path, "w", encoding="utf-8") as f:
            bibtexparser.dump(db, f, writer=writer)

    return changed


def main():
    repo_root, config = load_config()

    bib_paths = [repo_root / p for p in config["bib_files"]]
    any_changed = False

    for path in bib_paths:
        if not path.exists():
            continue
        print(f"Checking {path.name}...")
        if normalize_bib_file(path):
            any_changed = True
        else:
            print("  (all keys OK)")

    sys.exit(1 if any_changed else 0)


if __name__ == "__main__":
    main()
