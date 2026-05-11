"""Tests for discovery/approve.py -- approved citations to references.bib."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bib_utils import load_bib_entries
from discovery.analysis import save_citation
from discovery.approve import (
    _canonical_paper_type,
    _format_keywords,
    apply_bibtex_overrides,
    approve_citations,
)


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
        "suggested_project": "UCLA Miniscope v4",
        "suggested_keywords": ["Calcium Imaging", "Hippocampus", "Freely-Behaving"],
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
    def test_adds_project_field(self, sample_bibtex):
        overrides = {"project": "UCLA Miniscope v4"}
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "project" in result
        assert "UCLA Miniscope v4" in result

    def test_adds_paper_type_field(self, sample_bibtex):
        overrides = {"paper_type": "Science"}
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "paper_type" in result
        assert "Science" in result

    def test_adds_keywords_field(self, sample_bibtex):
        overrides = {"keywords": "Calcium Imaging, Hippocampus"}
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "keywords" in result
        assert "Calcium Imaging" in result
        assert "Hippocampus" in result

    def test_no_overrides(self, sample_bibtex):
        result = apply_bibtex_overrides(sample_bibtex, {})
        assert "@article" in result

    def test_multiple_overrides(self, sample_bibtex):
        overrides = {
            "project": "UCLA Miniscope v4",
            "paper_type": "Methods",
            "keywords": "Calcium Imaging, Memory",
        }
        result = apply_bibtex_overrides(sample_bibtex, overrides)
        assert "project" in result
        assert "paper_type" in result
        assert "keywords" in result


class TestCanonicalPaperType:
    def test_lowercase_to_title_case(self):
        assert _canonical_paper_type("science") == "Science"
        assert _canonical_paper_type("methods") == "Methods"
        assert _canonical_paper_type("review") == "Review"
        assert _canonical_paper_type("opinion") == "Opinion"
        assert _canonical_paper_type("protocol") == "Protocol"

    def test_underscore_to_space(self):
        assert _canonical_paper_type("tool_paper") == "Tool Paper"

    def test_already_canonical(self):
        assert _canonical_paper_type("Science") == "Science"
        assert _canonical_paper_type("Tool Paper") == "Tool Paper"

    def test_unrelated_returns_none(self):
        # `unrelated` papers should never reach pipeline/approved/, so they
        # don't have a canonical mapping. Return None so approve.py skips
        # writing the field.
        assert _canonical_paper_type("unrelated") is None

    def test_empty_and_unknown(self):
        assert _canonical_paper_type(None) is None
        assert _canonical_paper_type("") is None
        assert _canonical_paper_type("bogus_value") is None


class TestFormatKeywords:
    def test_list_to_csv(self):
        result = _format_keywords(["Calcium Imaging", "Memory", "Hippocampus"])
        assert result == "Calcium Imaging, Memory, Hippocampus"

    def test_string_passthrough(self):
        # Already-formatted string is re-normalized (trims whitespace).
        result = _format_keywords("Calcium Imaging,Memory , Hippocampus")
        assert result == "Calcium Imaging, Memory, Hippocampus"

    def test_empty_inputs(self):
        assert _format_keywords(None) is None
        assert _format_keywords([]) is None
        assert _format_keywords("") is None
        assert _format_keywords([""]) is None

    def test_drops_empty_items(self):
        result = _format_keywords(["Memory", "", "  ", "Hippocampus"])
        assert result == "Memory, Hippocampus"


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
        # project= from suggested_project
        assert "UCLA Miniscope v4" in content
        # paper_type= normalized from "science" → "Science"
        assert "Science" in content
        # keywords= joined from suggested_keywords list
        assert "Calcium Imaging" in content
        assert "Hippocampus" in content

    def test_legacy_suggested_component_fallback(
        self, pipeline_dirs, approved_citation, bib_file
    ):
        # Backward-compat: YAMLs analyzed before the rename used
        # `suggested_component` instead of `suggested_project`. approve.py
        # should still pick those up.
        approved_citation["analysis"].pop("suggested_project")
        approved_citation["analysis"]["suggested_component"] = "Minian"
        save_citation(pipeline_dirs["approved"] / "test.yaml", approved_citation)

        approve_citations(
            pipeline_root=pipeline_dirs["candidates"].parent,
            bib_path=bib_file,
        )

        content = bib_file.read_text()
        assert "project = {Minian}" in content

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
