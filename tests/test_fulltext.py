"""Tests for discovery/fulltext.py -- full text and BibTeX pre-fetching."""

import json
import sys
from pathlib import Path

import pytest
import responses
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from discovery.fulltext import (
    fetch_and_save_bibtex,
    fetch_and_save_fulltext,
    prefetch_candidate,
)


UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


@pytest.fixture
def candidate_yaml(pipeline_dirs, sample_candidate_data):
    """Write a candidate YAML to candidates/ and return its path."""
    path = pipeline_dirs["candidates"] / "test_candidate.yaml"
    with open(path, "w") as f:
        yaml.dump(sample_candidate_data, f, default_flow_style=False)
    return path


class TestFetchAndSaveBibtex:
    @responses.activate
    def test_saves_bibtex_file(self, candidate_yaml, sample_bibtex):
        responses.add(
            responses.GET,
            "https://doi.org/10.1038/s41467-023-39860-0",
            body=sample_bibtex,
            status=200,
            content_type="application/x-bibtex",
        )
        bib_path = fetch_and_save_bibtex(candidate_yaml)
        assert bib_path is not None
        assert bib_path.exists()
        assert bib_path.suffix == ".bib"
        content = bib_path.read_text()
        assert "@article" in content

    @responses.activate
    def test_updates_yaml_with_bibtex(self, candidate_yaml, sample_bibtex):
        responses.add(
            responses.GET,
            "https://doi.org/10.1038/s41467-023-39860-0",
            body=sample_bibtex,
            status=200,
            content_type="application/x-bibtex",
        )
        fetch_and_save_bibtex(candidate_yaml)
        data = yaml.safe_load(candidate_yaml.read_text())
        assert data["bibtex_source"] == "crossref"
        assert data["bibtex_raw"] is not None

    @responses.activate
    def test_returns_none_for_missing_doi(self, pipeline_dirs, sample_candidate_data):
        sample_candidate_data["doi"] = None
        path = pipeline_dirs["candidates"] / "no_doi.yaml"
        with open(path, "w") as f:
            yaml.dump(sample_candidate_data, f, default_flow_style=False)
        result = fetch_and_save_bibtex(path)
        assert result is None


class TestFetchAndSaveFulltext:
    @responses.activate
    def test_saves_fulltext_from_unpaywall_html(self, candidate_yaml):
        # Mock NCBI ID converter (returns no PMCID)
        responses.add(
            responses.GET,
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            json={"records": [{}]},
            status=200,
        )
        # Mock Unpaywall response with OA URL
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.1038/s41467-023-39860-0",
            json={
                "is_oa": True,
                "best_oa_location": {
                    "url": "https://example.com/article",
                    "url_for_pdf": None,
                    "host_type": "publisher",
                },
            },
            status=200,
        )
        # Mock the article page (must be >100 chars raw, >50 chars stripped)
        article_html = (
            "<html><body>"
            "<h1>Methods</h1>"
            "<p>We used the UCLA Miniscope v4 to perform calcium imaging of neural activity "
            "in freely behaving mice during fear conditioning experiments in the lab.</p>"
            "</body></html>"
        )
        responses.add(
            responses.GET,
            "https://example.com/article",
            body=article_html,
            status=200,
        )
        txt_path = fetch_and_save_fulltext(candidate_yaml, email="test@example.com")
        assert txt_path is not None
        assert txt_path.exists()
        content = txt_path.read_text()
        assert "Miniscope" in content

    @responses.activate
    def test_updates_yaml_fulltext_source(self, candidate_yaml):
        responses.add(
            responses.GET,
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            json={"records": [{}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.1038/s41467-023-39860-0",
            json={
                "is_oa": True,
                "best_oa_location": {
                    "url": "https://example.com/article",
                    "url_for_pdf": None,
                    "host_type": "publisher",
                },
            },
            status=200,
        )
        article_html = (
            "<html><body>"
            "<h1>Methods</h1>"
            "<p>We performed calcium imaging of neural activity in freely behaving mice "
            "during fear conditioning experiments using standard laboratory protocols.</p>"
            "</body></html>"
        )
        responses.add(
            responses.GET,
            "https://example.com/article",
            body=article_html,
            status=200,
        )
        fetch_and_save_fulltext(candidate_yaml, email="test@example.com")
        data = yaml.safe_load(candidate_yaml.read_text())
        assert data["fulltext"]["source"] == "unpaywall"

    @responses.activate
    def test_returns_none_when_no_oa(self, candidate_yaml):
        responses.add(
            responses.GET,
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            json={"records": [{}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.1038/s41467-023-39860-0",
            json={"is_oa": False, "best_oa_location": None},
            status=200,
        )
        result = fetch_and_save_fulltext(candidate_yaml, email="test@example.com")
        assert result is None
