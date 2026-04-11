"""Tests for discovery/candidates.py -- candidate generation and deduplication."""

import sys
from pathlib import Path

import pytest
import responses
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from discovery.candidates import (
    build_candidate,
    deduplicate_candidates,
    generate_candidates,
)

OPENALEX_BASE = "https://api.openalex.org"


class TestBuildCandidate:
    def test_builds_from_openalex_data(self, sample_openalex_work):
        from discovery.openalex import parse_openalex_work

        parsed = parse_openalex_work(sample_openalex_work)
        result = build_candidate(
            parsed,
            source="openalex_cites",
            seed_paper_doi="10.1038/s41593-019-0559-0",
            batch_id="test_batch",
        )
        assert result["doi"] == "10.1038/s41467-023-39860-0"
        assert result["source"] == "openalex_cites"
        assert result["seed_paper_doi"] == "10.1038/s41593-019-0559-0"
        assert result["stage"] == "candidate"
        assert result["analysis"]["status"] == "pending"
        assert result["bibtex_raw"] is None

    def test_generates_filename(self, sample_openalex_work):
        from discovery.openalex import parse_openalex_work

        parsed = parse_openalex_work(sample_openalex_work)
        result = build_candidate(parsed, "openalex_cites", "10.1234/test", "batch")
        # Should have a filename based on author_year_firstword
        assert "filename" in result
        assert result["filename"].endswith(".yaml")


class TestDeduplicateCandidates:
    def test_removes_doi_duplicates(self):
        candidates = [
            {"doi": "10.1234/a", "title": "Paper A", "publication_year": 2024},
            {"doi": "10.1234/a", "title": "Paper A Copy", "publication_year": 2024},
            {"doi": "10.1234/b", "title": "Paper B", "publication_year": 2024},
        ]
        result = deduplicate_candidates(candidates)
        assert len(result) == 2
        dois = {c["doi"] for c in result}
        assert dois == {"10.1234/a", "10.1234/b"}

    def test_removes_existing_bib_dois(self):
        candidates = [
            {"doi": "10.1234/a", "title": "Paper A", "publication_year": 2024},
            {"doi": "10.1234/b", "title": "Paper B", "publication_year": 2024},
        ]
        existing_dois = {"10.1234/a"}
        result = deduplicate_candidates(candidates, existing_dois=existing_dois)
        assert len(result) == 1
        assert result[0]["doi"] == "10.1234/b"

    def test_removes_existing_pipeline_dois(self):
        candidates = [
            {"doi": "10.1234/a", "title": "Paper A", "publication_year": 2024},
        ]
        pipeline_dois = {"10.1234/a"}
        result = deduplicate_candidates(candidates, pipeline_dois=pipeline_dois)
        assert len(result) == 0

    def test_removes_seed_paper_dois(self):
        candidates = [
            {"doi": "10.1038/s41593-019-0559-0", "title": "Seed Paper", "publication_year": 2019},
            {"doi": "10.1234/b", "title": "Real Paper", "publication_year": 2024},
        ]
        seed_dois = {"10.1038/s41593-019-0559-0"}
        result = deduplicate_candidates(candidates, seed_dois=seed_dois)
        assert len(result) == 1
        assert result[0]["doi"] == "10.1234/b"

    def test_keeps_none_doi_candidates(self):
        candidates = [
            {"doi": None, "title": "No DOI Paper", "publication_year": 2024, "openalex_id": "W123"},
            {"doi": "10.1234/a", "title": "Has DOI", "publication_year": 2024},
        ]
        result = deduplicate_candidates(candidates)
        assert len(result) == 2

    def test_deduplicates_none_doi_by_title_year(self):
        candidates = [
            {"doi": None, "title": "Same Title", "publication_year": 2024, "openalex_id": "W1"},
            {"doi": None, "title": "Same Title", "publication_year": 2024, "openalex_id": "W2"},
        ]
        result = deduplicate_candidates(candidates)
        assert len(result) == 1


class TestGenerateCandidates:
    @responses.activate
    def test_generates_yaml_files(self, sample_discovery_config, sample_openalex_work, pipeline_dirs):
        # Mock OpenAlex resolve
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works/https://doi.org/10.1038/s41593-019-0559-0",
            json={"id": "https://openalex.org/W2964321694"},
            status=200,
        )
        # Mock OpenAlex citing works
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works",
            json={
                "meta": {"count": 1, "per_page": 50, "next_cursor": None},
                "results": [sample_openalex_work],
            },
            status=200,
        )

        files = generate_candidates(
            config_path=sample_discovery_config,
            pipeline_root=pipeline_dirs["candidates"].parent,
        )
        assert len(files) == 1
        assert files[0].exists()
        data = yaml.safe_load(files[0].read_text())
        assert data["doi"] == "10.1038/s41467-023-39860-0"
        assert data["stage"] == "candidate"

    @responses.activate
    def test_skips_existing_pipeline_dois(self, sample_discovery_config, sample_openalex_work, pipeline_dirs):
        # Pre-populate pipeline with same DOI
        from discovery.analysis import save_citation
        save_citation(
            pipeline_dirs["reviewed"] / "existing.yaml",
            {"doi": "10.1038/s41467-023-39860-0", "stage": "reviewed"},
        )

        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works/https://doi.org/10.1038/s41593-019-0559-0",
            json={"id": "https://openalex.org/W2964321694"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works",
            json={
                "meta": {"count": 1, "per_page": 50, "next_cursor": None},
                "results": [sample_openalex_work],
            },
            status=200,
        )

        files = generate_candidates(
            config_path=sample_discovery_config,
            pipeline_root=pipeline_dirs["candidates"].parent,
        )
        assert len(files) == 0
