"""Candidate generation and deduplication for citation discovery."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bib_utils import generate_key, load_bib_entries, normalize_title

from discovery.analysis import get_existing_pipeline_dois, save_citation
from discovery.config import load_discovery_config
from discovery.openalex import find_citing_works, resolve_doi_to_openalex


def build_candidate(parsed_work, source, seed_paper_doi, batch_id):
    """Build a full candidate YAML data dict from a parsed OpenAlex work.

    Adds provenance, empty analysis fields, and generates a filename.
    """
    # Generate a filename from author/year/title
    author_str = ""
    if parsed_work.get("authors"):
        first = parsed_work["authors"][0]
        author_str = first.get("last", "unknown")
    year = str(parsed_work.get("publication_year", "0000"))
    title = parsed_work.get("title", "untitled")

    entry_for_key = {"author": author_str, "year": year, "title": title}
    key = generate_key(entry_for_key)
    filename = f"{key}.yaml"

    return {
        "doi": parsed_work.get("doi"),
        "openalex_id": parsed_work.get("openalex_id"),
        "pmid": None,
        "pmcid": None,
        "title": parsed_work.get("title"),
        "authors": parsed_work.get("authors", []),
        "journal": parsed_work.get("journal"),
        "publication_year": parsed_work.get("publication_year"),
        "publication_date": parsed_work.get("publication_date"),
        "is_retracted": parsed_work.get("is_retracted", False),
        "open_access": parsed_work.get("open_access", {}),
        "source": source,
        "seed_paper_doi": seed_paper_doi,
        "discovered_date": date.today().isoformat(),
        "batch_id": batch_id,
        "bibtex_raw": None,
        "bibtex_source": None,
        "fulltext": {"source": None, "pdf_local_path": None},
        "analysis": {
            "status": "pending",
            "uses_tool": None,
            "confidence": None,
            "tools_identified": [],
            "evidence": [],
            "paper_type": None,
            "suggested_component": None,
            "suggested_technique": None,
            "reasoning": None,
        },
        "stage": "candidate",
        "stage_history": [
            {"stage": "candidate", "timestamp": datetime.now(timezone.utc).isoformat()},
        ],
        "filename": filename,
    }


def deduplicate_candidates(
    candidates,
    existing_dois=None,
    pipeline_dois=None,
    seed_dois=None,
):
    """Remove duplicate candidates.

    Deduplicates by:
    1. DOI (exact match) against other candidates in the batch
    2. DOI against papers already in references.bib (existing_dois)
    3. DOI against papers already in the pipeline (pipeline_dois)
    4. DOI against seed papers themselves (seed_dois)
    5. Title+year for candidates without DOIs
    """
    existing_dois = existing_dois or set()
    pipeline_dois = pipeline_dois or set()
    seed_dois = seed_dois or set()

    seen_dois = set()
    seen_title_years = set()
    unique = []

    for candidate in candidates:
        doi = candidate.get("doi")
        title = candidate.get("title", "")
        year = candidate.get("publication_year")

        if doi:
            # Skip if DOI already seen in this batch
            if doi in seen_dois:
                continue
            # Skip if DOI is in references.bib
            if doi in existing_dois:
                continue
            # Skip if DOI is already in pipeline
            if doi in pipeline_dois:
                continue
            # Skip if DOI is a seed paper
            if doi in seed_dois:
                continue
            seen_dois.add(doi)
        else:
            # For no-DOI papers, deduplicate by normalized title + year
            norm_title = normalize_title(title) if title else ""
            key = (norm_title, year)
            if key in seen_title_years:
                continue
            seen_title_years.add(key)

        unique.append(candidate)

    return unique


def generate_candidates(config_path=None, pipeline_root=None, from_date=None):
    """Generate candidate YAML files from all configured sources.

    Args:
        config_path: Path to discovery_config.yaml (or None for default).
        pipeline_root: Path to pipeline/ directory (or None for default).
        from_date: Optional date string (YYYY-MM-DD) to only find papers
                   published after this date. Used for weekly discovery.

    Returns:
        List of Path objects for created YAML files.
    """
    config = load_discovery_config(config_path)

    if pipeline_root is None:
        repo_root = Path(__file__).resolve().parent.parent
        pipeline_root = repo_root / "pipeline"
    pipeline_root = Path(pipeline_root)

    email = config.get("apis", {}).get("openalex_email")
    batch_id = f"{'weekly' if from_date else 'backlog'}_{date.today().isoformat()}"

    # Collect existing DOIs to skip
    repo_root = Path(__file__).resolve().parent.parent
    bib_paths = [repo_root / p for p in config.get("bib_files", ["references.bib"])]
    existing_entries = load_bib_entries(bib_paths)
    existing_dois = {
        e.get("doi", "").strip().lower()
        for e in existing_entries.values()
        if e.get("doi")
    }

    pipeline_dois = get_existing_pipeline_dois(pipeline_root)
    seed_dois = {s["doi"] for s in config["seed_papers"]}

    # Gather all candidates from OpenAlex citation graphs
    all_candidates = []

    for seed in config["seed_papers"]:
        # Resolve OpenAlex ID if not cached
        oa_id = seed.get("openalex_id")
        if not oa_id:
            oa_id = resolve_doi_to_openalex(seed["doi"], email=email)
            if not oa_id:
                print(f"  Warning: could not resolve OpenAlex ID for {seed['doi']}")
                continue
            seed["openalex_id"] = oa_id

        works = find_citing_works(oa_id, email=email, from_date=from_date)

        for work in works:
            candidate = build_candidate(
                work,
                source="openalex_cites",
                seed_paper_doi=seed["doi"],
                batch_id=batch_id,
            )
            all_candidates.append(candidate)

    # Deduplicate
    unique = deduplicate_candidates(
        all_candidates,
        existing_dois=existing_dois,
        pipeline_dois=pipeline_dois,
        seed_dois=seed_dois,
    )

    # Write YAML files to candidates/
    candidates_dir = pipeline_root / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    seen_filenames = set()
    for candidate in unique:
        filename = candidate.pop("filename")
        # Handle filename collisions (different papers with same author_year_firstword)
        base = filename.removesuffix(".yaml")
        final_filename = filename
        suffix_idx = 0
        while final_filename in seen_filenames or (candidates_dir / final_filename).exists():
            suffix_idx += 1
            suffix = chr(ord("a") + suffix_idx - 1)
            final_filename = f"{base}_{suffix}.yaml"
        seen_filenames.add(final_filename)

        path = candidates_dir / final_filename
        save_citation(path, candidate)
        created_files.append(path)

    return created_files
