"""Move approved citations into references.bib.

Reads YAML files from pipeline/approved/, extracts BibTeX, applies overrides
(component, technique, etc.), normalizes keys, checks for duplicates, and
appends to references.bib.
"""

import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bwriter import BibTexWriter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bib_utils import generate_key, load_bib_entries, make_parser

from discovery.analysis import list_citations, load_citation


def apply_bibtex_overrides(bibtex_str, overrides):
    """Add or replace fields in a BibTeX entry string.

    Used to inject component, technique, project fields from analysis results.
    """
    if not overrides:
        return bibtex_str

    parser = make_parser()
    db = bibtexparser.loads(bibtex_str, parser=parser)
    if not db.entries:
        return bibtex_str

    entry = db.entries[0]
    for key, value in overrides.items():
        if value:
            entry[key] = value

    writer = BibTexWriter()
    writer.indent = "  "
    return bibtexparser.dumps(db, writer=writer)


def approve_citations(pipeline_root=None, bib_path=None):
    """Process all approved citation YAML files into references.bib.

    Returns:
        Dict with 'added' and 'skipped' counts.
    """
    if pipeline_root is None:
        repo_root = Path(__file__).resolve().parent.parent
        pipeline_root = repo_root / "pipeline"
    pipeline_root = Path(pipeline_root)

    if bib_path is None:
        repo_root = Path(__file__).resolve().parent.parent
        bib_path = repo_root / "references.bib"
    bib_path = Path(bib_path)

    # Load existing entries to check for duplicates
    existing = load_bib_entries([bib_path]) if bib_path.exists() else {}
    existing_dois = {
        e.get("doi", "").strip().lower()
        for e in existing.values()
        if e.get("doi")
    }

    approved_files = list_citations("approved", pipeline_root)
    stats = {"added": 0, "skipped": 0}

    for filepath in approved_files:
        data = load_citation(filepath)
        bibtex_raw = data.get("bibtex_raw")
        if not bibtex_raw:
            print(f"  Skipping {filepath.name}: no BibTeX data")
            stats["skipped"] += 1
            continue

        # Check for duplicate DOI
        doi = data.get("doi", "")
        if doi and doi.strip().lower() in existing_dois:
            print(f"  Skipping {filepath.name}: DOI already in references.bib")
            stats["skipped"] += 1
            continue

        # Build overrides from analysis results
        analysis = data.get("analysis", {})
        overrides = {}
        if analysis.get("suggested_component"):
            overrides["component"] = analysis["suggested_component"]
        if analysis.get("suggested_technique"):
            overrides["technique"] = analysis["suggested_technique"]

        # Apply overrides and normalize key
        bibtex = apply_bibtex_overrides(bibtex_raw, overrides)

        parser = make_parser()
        db = bibtexparser.loads(bibtex, parser=parser)
        if not db.entries:
            print(f"  Skipping {filepath.name}: could not parse BibTeX")
            stats["skipped"] += 1
            continue

        entry = db.entries[0]
        entry["ID"] = generate_key(entry)

        # Append to bib file
        writer = BibTexWriter()
        writer.indent = "  "
        entry_str = bibtexparser.dumps(db, writer=writer)

        with open(bib_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry_str)

        # Track the new DOI so we don't add it twice in the same run
        if doi:
            existing_dois.add(doi.strip().lower())

        stats["added"] += 1
        print(f"  Added {entry['ID']} from {filepath.name}")

    return stats


def main():
    stats = approve_citations()
    print(f"\nDone: {stats['added']} added, {stats['skipped']} skipped")


if __name__ == "__main__":
    main()
