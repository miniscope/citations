"""Tests for discovery/approve.py -- approved citations to references.bib."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bib_utils import load_bib_entries
from discovery.analysis import save_citation
from discovery.approve import approve_citations, apply_bibtex_overrides


@pytest.fixture
def approved_citation(sample_candidate_data, sample_bibtex):
    """A citation that has been reviewed and approved with BibTeX."""
    data = dict(sample_candidate_data)
    data["stage"] = "approved"
    data["bibtex_raw"] = sample_bibtex
    data["bibtex_source"] = "crossref"
    data["analysis"] = {
        "status": "completed",
        "uses_tool": True,
        "confidence": 0.9,
        "tools_identified": [
            {"tool": "UCLA Miniscope v4", "confidence": 0.9, "section": "methods"}
        ],
        "evidence": [{"text": "We used the UCLA Miniscope v4", "section": "Methods"}],
        "paper_type": "science",
        "suggested_component": "UCLA Miniscope v4",
        "suggested_technique": "Calcium Imaging",
        "reasoning": "Clear tool usage in methods.",
    }
    return data


@pytest.fixture
def bib_file(tmp_path):
    """Create an empty references.bib file."""
    path = tmp_path / "references.bib"
    path.write_text("")
    return path


class TestApplyBibtexOverrides:
    def test_adds_component_field(self, sample_bibtex):
        overrides = {"component": "UCLA Miniscope v4"}
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "component" in result
        assert "UCLA Miniscope v4" in result

    def test_adds_technique_field(self, sample_bibtex):
        overrides = {"technique": "Calcium Imaging"}
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "technique" in result
        assert "Calcium Imaging" in result

    def test_no_overrides(self, sample_bibtex):
        result = apply_bibtex_overrides(sample_bibtex, {})
        assert "@article" in result

    def test_multiple_overrides(self, sample_bibtex):
        overrides = {
            "component": "UCLA Miniscope v4",
            "technique": "Calcium Imaging",
            "project": "UCLA Miniscope Project",
        }
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "component" in result
        assert "technique" in result
        assert "project" in result


class TestApproveCitations:
    def test_appends_to_bib(self, pipeline_dirs, approved_citation, bib_file):
        save_citation(pipeline_dirs["approved"] / "test.yaml", approved_citation)

        stats = approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )
        assert stats["added"] == 1
        assert stats["skipped"] == 0

        # Verify the entry is in the bib file
        entries = load_bib_entries([bib_file])
        assert len(entries) == 1

    def test_skips_duplicate_doi(self, pipeline_dirs, approved_citation, bib_file):
        # Pre-populate bib with same DOI
        bib_file.write_text(
            "@article{existing_2023_test,\n"
            "  title = {Existing},\n"
            "  doi = {10.1038/s41467-023-39860-0},\n"
            "  year = {2023}\n"
            "}\n"
        )

        save_citation(pipeline_dirs["approved"] / "test.yaml", approved_citation)

        stats = approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )
        assert stats["added"] == 0
        assert stats["skipped"] == 1

    def test_applies_suggested_overrides(self, pipeline_dirs, approved_citation, bib_file):
        save_citation(pipeline_dirs["approved"] / "test.yaml", approved_citation)

        approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )

        content = bib_file.read_text()
        assert "UCLA Miniscope v4" in content
        assert "Calcium Imaging" in content

    def test_empty_approved_dir(self, pipeline_dirs, bib_file):
        stats = approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )
        assert stats["added"] == 0
        assert stats["skipped"] == 0

    def test_normalizes_keys(self, pipeline_dirs, approved_citation, bib_file):
        save_citation(pipeline_dirs["approved"] / "test.yaml", approved_citation)

        approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )

        entries = load_bib_entries([bib_file])
        keys = list(entries.keys())
        assert len(keys) == 1
        # Key should be normalized (lowercase, author_year_word format)
        assert keys[0] == keys[0].lower()
