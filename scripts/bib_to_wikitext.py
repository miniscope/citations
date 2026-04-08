#!/usr/bin/env python3
"""Convert BibTeX entries to MediaWiki wikitext for the Publication ontology category.

Generates one .wikitext file per BibTeX entry under output/, using template
invocations compatible with SemanticSchemas-generated templates.
"""

import json
import os
import re
import sys

from bib_utils import (
    build_template_call,
    clean_latex,
    entry_changed,
    load_base_entries,
    load_bib_entries,
    load_config,
)

# BibTeX entry type → ontology Has_publication_type allowed value
ENTRY_TYPE_MAP = {
    "article": "Journal Article",
    "inproceedings": "Conference Paper",
    "conference": "Conference Paper",
    "incollection": "Book Chapter",
    "phdthesis": "Thesis",
    "mastersthesis": "Thesis",
    "book": "Book Chapter",
    "unpublished": "Preprint",
}

# BibTeX field → Publication template parameter name
# (SemanticSchemas NamingHelper: remove "Has " prefix, lowercase, spaces→underscores)
FIELD_MAP = {
    "doi": "doi",
    "journal": "journal",
    "booktitle": "journal",  # conference proceedings → journal field
    "volume": "volume",
    "number": "issue",
    "pages": "pages",
    "abstract": "abstract",
    "keywords": "keyword",
    "url": "website",
    "pmid": "pubmed_id",
    # Custom fields for ontology cross-links
    "project": "project",
    "component": "component",
    "equipment": "equipment_used",
    "technique": "technique",
    "attachment": "attachment",
    "publication_status": "publication_status",
}



def parse_author_name(name_str):
    """Parse a single author name string into first/middle/last parts.

    Handles both "Last, First Middle" and "First Middle Last" formats.
    """
    name_str = clean_latex(name_str.strip())
    if not name_str:
        return {}

    if "," in name_str:
        # "Last, First Middle" or "Last, Jr., First"
        parts = [p.strip() for p in name_str.split(",")]
        last_name = parts[0]
        first_parts = parts[-1].split() if len(parts) >= 2 else []
    else:
        # "First Middle Last"
        words = name_str.split()
        if len(words) == 1:
            return {"last_name": words[0]}
        last_name = words[-1]
        first_parts = words[:-1]

    result = {"last_name": last_name}
    if first_parts:
        result["first_name"] = first_parts[0]
        if len(first_parts) > 1:
            result["middle_name"] = " ".join(first_parts[1:])
    return result


def entry_to_wikitext(entry):
    """Convert a single BibTeX entry dict to full Publication page wikitext."""
    entry_type = entry.get("ENTRYTYPE", "misc")

    # -- Main Publication template params --
    params = {}

    # Title → description (inherited from Document)
    if "title" in entry:
        params["description"] = clean_latex(entry["title"])

    # Document parent fields
    params["document_type"] = "Publication"
    if "year" in entry:
        params["document_date"] = entry["year"]

    # Publication status
    params["publication_status"] = "Published"
    if entry_type == "unpublished":
        params["publication_status"] = "Preprint"
    elif entry_type == "misc":
        if "eprint" in entry or "arxivid" in entry:
            params["publication_status"] = "Preprint"

    # Publication year
    if "year" in entry:
        params["publication_year"] = entry["year"]

    # Publication type
    pub_type = ENTRY_TYPE_MAP.get(entry_type)
    if pub_type:
        params["publication_type"] = pub_type

    # Mapped fields
    for bib_field, param_name in FIELD_MAP.items():
        if bib_field in entry and param_name not in params:
            value = clean_latex(entry[bib_field])
            if bib_field == "pages":
                value = value.replace("--", "\u2013")
            params[param_name] = value

    main_block = build_template_call("Publication", params)

    # -- Author subobject template calls --
    author_blocks = []
    if "author" in entry:
        # bibtexparser v1 gives author as a single string with " and " separators
        author_str = entry["author"]
        authors = [a.strip() for a in re.split(r"\s+and\s+", author_str)]

        for i, author_name in enumerate(authors):
            a_params = parse_author_name(author_name)
            if not a_params:
                continue
            if i == 0:
                a_params["is_first_author"] = "Yes"

            author_blocks.append(
                build_template_call("Subobject/Has publication author", a_params)
            )

    # -- Assemble page --
    marker_content = main_block
    if author_blocks:
        marker_content += "\n\n" + "\n\n".join(author_blocks)

    page = (
        f"<!-- citations-sync start -->\n"
        f"{marker_content}\n"
        f"<!-- citations-sync end -->\n"
        f"[[Category:Publication]]"
    )

    return page


def generate_page_title(entry, config):
    """Generate the wiki page title from a BibTeX entry."""
    prefix = config.get("page_prefix", "Publication/")
    namespace = config.get("page_namespace", "")
    if namespace:
        return f"{namespace}:{prefix}{entry['ID']}"
    return f"{prefix}{entry['ID']}"


def main():
    repo_root, config = load_config()

    bib_paths = [repo_root / p for p in config["bib_files"]]
    missing = [p for p in bib_paths if not p.exists()]
    if missing:
        print(f"Error: missing bib files: {missing}", file=sys.stderr)
        sys.exit(1)

    entries = list(load_bib_entries(bib_paths).values())

    # If --changed-only is passed, filter to added/modified entries
    changed_only = "--changed-only" in sys.argv
    base_ref = os.environ.get("BASE_REF", "HEAD~1")
    changed_keys = None

    removed_entries = []

    if changed_only:
        base_entries = load_base_entries(config["bib_files"], base_ref)
        current_keys = {e["ID"] for e in entries}
        changed_keys = set()
        for entry in entries:
            key = entry["ID"]
            if key not in base_entries:
                changed_keys.add(key)  # new entry
            elif entry_changed(base_entries[key], entry):
                changed_keys.add(key)  # modified entry
        # Detect entries removed since base
        for key in base_entries:
            if key not in current_keys:
                removed_entries.append({
                    "key": key,
                    "page_title": generate_page_title(base_entries[key], config),
                })
        print(f"Changed entries: {len(changed_keys)} of {len(entries)}")
        if removed_entries:
            print(f"Removed entries: {len(removed_entries)}")

    output_dir = repo_root / "output"
    output_dir.mkdir(exist_ok=True)

    manifest = {}
    for entry in entries:
        key = entry["ID"]
        if changed_keys is not None and key not in changed_keys:
            continue

        wikitext = entry_to_wikitext(entry)
        page_title = generate_page_title(entry, config)
        filename = key + ".wikitext"

        (output_dir / filename).write_text(wikitext, encoding="utf-8")
        manifest[key] = {"page_title": page_title, "file": filename}
        print(f"  {key} -> {page_title}")

    # Write manifest for the push script
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({"entries": manifest, "deleted": removed_entries}, f, indent=2)

    count = len(manifest)
    total = len(entries)
    if changed_keys is not None:
        print(f"\nConverted {count} changed entries (of {total} total) -> output/")
    else:
        print(f"\nConverted {total} entries -> output/")


if __name__ == "__main__":
    main()
