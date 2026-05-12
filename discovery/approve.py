"""Move approved citations into references.bib.

Reads YAML files from pipeline/approved/, extracts BibTeX, applies overrides
(project, paper_type, keywords from analysis), normalizes keys, checks for
duplicates, and appends to references.bib.
"""

import sys
from pathlib import Path

import bibtexparser
from bibtexparser.bwriter import BibTexWriter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bib_utils import generate_key, load_bib_entries, make_parser

from discovery.analysis import list_citations, load_citation


# Map the LLM agent's lowercase paper_type values to the canonical Title Case
# values defined in vocabulary.yaml / SchemaSync. The agent prompt currently
# emits `science | methods | software | tool_paper | review | unrelated` while
# the schema enum is `Science, Methods, Software, Tool Paper, Review,
# Opinion, Protocol`. `unrelated` papers should never reach pipeline/approved/
# so we drop them; new values (`Opinion`, `Protocol`) come from the curator
# overriding `analysis.paper_type` during triage.
_PAPER_TYPE_CANONICAL = {
    "science": "Science",
    "methods": "Methods",
    "software": "Software",
    "analysis_pipeline": "Analysis Pipeline",
    "tool_paper": "Tool Paper",
    "review": "Review",
    "opinion": "Opinion",
    "protocol": "Protocol",
}


def _canonical_paper_type(value):
    """Normalize a paper_type value to its canonical Title Case form.

    Accepts both the LLM-agent lowercase form (`science`) and the canonical
    Title Case form (`Science`). Returns None for `unrelated`, empty, or
    unknown values.
    """
    if not value:
        return None
    key = str(value).strip().lower().replace(" ", "_")
    return _PAPER_TYPE_CANONICAL.get(key)


def _format_keywords(value):
    """Normalize keywords to a comma-separated string for BibTeX.

    Accepts a list, a comma-separated string, or None; returns the
    canonical comma-separated form (or None if empty after trimming).
    """
    if not value:
        return None
    if isinstance(value, str):
        items = [k.strip() for k in value.split(",")]
    else:
        items = [str(k).strip() for k in value]
    items = [k for k in items if k]
    return ", ".join(items) if items else None


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

        # Build overrides from analysis results.
        # `suggested_component` is the legacy field name from before the
        # Has component → Has project rename; accept it as a fallback so
        # YAMLs analyzed before the schema simplification still work.
        analysis = data.get("analysis", {})
        overrides = {}
        project = analysis.get("suggested_project") or analysis.get("suggested_component")
        if project:
            overrides["project"] = project
        paper_type = _canonical_paper_type(analysis.get("paper_type"))
        if paper_type:
            overrides["paper_type"] = paper_type
        keywords = _format_keywords(analysis.get("suggested_keywords"))
        if keywords:
            overrides["keywords"] = keywords

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
