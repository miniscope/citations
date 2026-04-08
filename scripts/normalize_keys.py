#!/usr/bin/env python3
"""Normalize BibTeX citation keys to a consistent format.

Rewrites keys in .bib files to: {first_author_lastname}_{year}_{first_title_word}
All lowercase, spaces replaced with underscores. Duplicates get _a, _b suffixes.

Exits with code 0 if no changes, 1 if keys were rewritten.
"""

import re
import sys
import unicodedata

import bibtexparser
from bibtexparser.bwriter import BibTexWriter

from bib_utils import clean_latex, load_config, make_parser

STOP_WORDS = {"a", "an", "the", "of", "and", "in", "for", "on", "to", "with", "by", "is", "are"}


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
