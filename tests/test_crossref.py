"""Tests for discovery/crossref.py -- BibTeX fetching from CrossRef."""

import pytest
import responses

from discovery.crossref import fetch_bibtex, validate_bibtex, normalize_bibtex_key


class TestFetchBibtex:
    @responses.activate
    def test_fetches_bibtex_for_valid_doi(self, sample_bibtex):
        responses.add(
            responses.GET,
            "https://doi.org/10.1038/s41467-023-39860-0",
            body=sample_bibtex,
            status=200,
            content_type="application/x-bibtex",
        )
        result = fetch_bibtex("10.1038/s41467-023-39860-0")
        assert result is not None
        assert "@article" in result

    @responses.activate
    def test_returns_none_for_missing_doi(self):
        responses.add(
            responses.GET,
            "https://doi.org/10.9999/nonexistent",
            body="Not Found",
            status=404,
        )
        result = fetch_bibtex("10.9999/nonexistent")
        assert result is None

    @responses.activate
    def test_returns_none_on_timeout(self):
        responses.add(
            responses.GET,
            "https://doi.org/10.1234/timeout",
            body=ConnectionError("timeout"),
        )
        result = fetch_bibtex("10.1234/timeout")
        assert result is None

    @responses.activate
    def test_sends_bibtex_accept_header(self, sample_bibtex):
        responses.add(
            responses.GET,
            "https://doi.org/10.1234/test",
            body=sample_bibtex,
            status=200,
        )
        fetch_bibtex("10.1234/test")
        assert "application/x-bibtex" in responses.calls[0].request.headers["Accept"]


class TestValidateBibtex:
    def test_valid_bibtex(self, sample_bibtex):
        assert validate_bibtex(sample_bibtex) is True

    def test_invalid_bibtex(self):
        assert validate_bibtex("this is not bibtex") is False

    def test_empty_string(self):
        assert validate_bibtex("") is False


class TestNormalizeBibtexKey:
    def test_normalizes_key(self, sample_bibtex):
        result = normalize_bibtex_key(sample_bibtex)
        assert "zhang_2023_large" in result

    def test_preserves_content(self, sample_bibtex):
        result = normalize_bibtex_key(sample_bibtex)
        assert "Nature Communications" in result
        assert "10.1038/s41467-023-39860-0" in result
