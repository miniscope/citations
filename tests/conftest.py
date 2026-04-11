"""Shared fixtures for citation discovery tests."""

import shutil
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to the static test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def pipeline_dirs(tmp_path):
    """Create a temporary pipeline directory structure.

    Returns a dict mapping stage names to their Path objects.
    """
    stages = ["candidates", "in-progress", "reviewed", "approved", "rejected"]
    dirs = {}
    for stage in stages:
        d = tmp_path / "pipeline" / stage
        d.mkdir(parents=True)
        dirs[stage] = d
    return dirs


@pytest.fixture
def sample_openalex_work():
    """A single OpenAlex work object as returned by the API."""
    return {
        "id": "https://openalex.org/W4384829205",
        "doi": "https://doi.org/10.1038/s41467-023-39860-0",
        "title": "Large depth-of-field ultra-compact microscope by progressive optimization",
        "publication_date": "2023-07-11",
        "publication_year": 2023,
        "type": "article",
        "is_retracted": False,
        "authorships": [
            {
                "author_position": "first",
                "author": {
                    "id": "https://openalex.org/A1234",
                    "display_name": "Yuanlong Zhang",
                },
            },
            {
                "author_position": "middle",
                "author": {
                    "id": "https://openalex.org/A5678",
                    "display_name": "Jiamin Wu",
                },
            },
        ],
        "primary_location": {
            "source": {
                "display_name": "Nature Communications",
            },
        },
        "open_access": {
            "is_oa": True,
            "oa_status": "gold",
            "oa_url": "https://www.nature.com/articles/s41467-023-39860-0.pdf",
        },
        "cited_by_count": 15,
    }


@pytest.fixture
def sample_bibtex():
    """A valid BibTeX entry as returned by CrossRef."""
    return (
        "@article{Zhang_2023,\n"
        "  title = {Large depth-of-field ultra-compact microscope},\n"
        "  author = {Zhang, Yuanlong and Wu, Jiamin},\n"
        "  journal = {Nature Communications},\n"
        "  volume = {14},\n"
        "  year = {2023},\n"
        "  doi = {10.1038/s41467-023-39860-0}\n"
        "}"
    )


@pytest.fixture
def sample_candidate_data(sample_openalex_work):
    """A candidate citation YAML data dict."""
    return {
        "doi": "10.1038/s41467-023-39860-0",
        "openalex_id": "W4384829205",
        "pmid": None,
        "pmcid": None,
        "title": "Large depth-of-field ultra-compact microscope by progressive optimization",
        "authors": [
            {"first": "Yuanlong", "last": "Zhang"},
            {"first": "Jiamin", "last": "Wu"},
        ],
        "journal": "Nature Communications",
        "publication_year": 2023,
        "is_retracted": False,
        "open_access": {
            "is_oa": True,
            "oa_url": "https://www.nature.com/articles/s41467-023-39860-0.pdf",
        },
        "source": "openalex_cites",
        "seed_paper_doi": "10.1038/s41593-019-0559-0",
        "discovered_date": "2026-04-10",
        "batch_id": "backlog_2026-04-10",
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
            {"stage": "candidate", "timestamp": "2026-04-10T10:00:00Z"},
        ],
    }


@pytest.fixture
def sample_discovery_config(tmp_path):
    """Create a temporary discovery_config.yaml and return its path."""
    import yaml

    config = {
        "seed_papers": [
            {
                "doi": "10.1038/s41593-019-0559-0",
                "short_name": "Shuman et al. 2019",
                "openalex_id": None,
            },
        ],
        "tools": [
            {
                "name": "UCLA Miniscope v4",
                "aliases": ["Miniscope v4", "open-source miniscope"],
                "wiki_component": "UCLA Miniscope v4",
            },
        ],
        "search_keywords": ["UCLA Miniscope"],
        "apis": {
            "openalex_email": "test@example.com",
            "unpaywall_email": "test@example.com",
        },
        "processing": {
            "max_parallel_agents": 5,
            "abstract_only_max_confidence": 0.5,
        },
        "last_discovery_run": None,
    }
    config_path = tmp_path / "discovery_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    return config_path
