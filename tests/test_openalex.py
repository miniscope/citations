"""Tests for discovery/openalex.py -- OpenAlex API client."""

import json

import pytest
import responses

from discovery.openalex import (
    find_citing_works,
    resolve_doi_to_openalex,
    parse_openalex_work,
)


OPENALEX_BASE = "https://api.openalex.org"


@pytest.fixture
def openalex_works_response(sample_openalex_work):
    """A paginated response from the OpenAlex works endpoint."""
    return {
        "meta": {"count": 1, "per_page": 50, "next_cursor": None},
        "results": [sample_openalex_work],
    }


class TestParseOpenalexWork:
    def test_extracts_doi(self, sample_openalex_work):
        result = parse_openalex_work(sample_openalex_work)
        assert result["doi"] == "10.1038/s41467-023-39860-0"

    def test_extracts_openalex_id(self, sample_openalex_work):
        result = parse_openalex_work(sample_openalex_work)
        assert result["openalex_id"] == "W4384829205"

    def test_extracts_authors(self, sample_openalex_work):
        result = parse_openalex_work(sample_openalex_work)
        assert len(result["authors"]) == 2
        assert result["authors"][0]["last"] == "Zhang"
        assert result["authors"][0]["first"] == "Yuanlong"

    def test_extracts_journal(self, sample_openalex_work):
        result = parse_openalex_work(sample_openalex_work)
        assert result["journal"] == "Nature Communications"

    def test_handles_missing_doi(self, sample_openalex_work):
        sample_openalex_work["doi"] = None
        result = parse_openalex_work(sample_openalex_work)
        assert result["doi"] is None

    def test_handles_retracted(self, sample_openalex_work):
        sample_openalex_work["is_retracted"] = True
        result = parse_openalex_work(sample_openalex_work)
        assert result["is_retracted"] is True


class TestFindCitingWorks:
    @responses.activate
    def test_basic_query(self, openalex_works_response):
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works",
            json=openalex_works_response,
            status=200,
        )
        results = find_citing_works("W1234567890", email="test@example.com")
        assert len(results) == 1
        assert results[0]["doi"] == "10.1038/s41467-023-39860-0"

    @responses.activate
    def test_with_date_filter(self, openalex_works_response):
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works",
            json=openalex_works_response,
            status=200,
        )
        results = find_citing_works(
            "W1234567890", email="test@example.com", from_date="2024-01-01"
        )
        assert len(results) == 1
        # Verify the request included the date filter
        assert "from_publication_date" in responses.calls[0].request.url

    @responses.activate
    def test_pagination(self, sample_openalex_work):
        page1 = {
            "meta": {"count": 2, "per_page": 1, "next_cursor": "cursor123"},
            "results": [sample_openalex_work],
        }
        work2 = dict(sample_openalex_work)
        work2["doi"] = "https://doi.org/10.9999/other"
        work2["id"] = "https://openalex.org/W9999999999"
        page2 = {
            "meta": {"count": 2, "per_page": 1, "next_cursor": None},
            "results": [work2],
        }
        responses.add(responses.GET, f"{OPENALEX_BASE}/works", json=page1, status=200)
        responses.add(responses.GET, f"{OPENALEX_BASE}/works", json=page2, status=200)

        results = find_citing_works("W1234567890", email="test@example.com")
        assert len(results) == 2

    @responses.activate
    def test_empty_results(self):
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works",
            json={"meta": {"count": 0, "per_page": 50, "next_cursor": None}, "results": []},
            status=200,
        )
        results = find_citing_works("W1234567890", email="test@example.com")
        assert results == []

    @responses.activate
    def test_filters_retracted(self, sample_openalex_work):
        sample_openalex_work["is_retracted"] = True
        response = {
            "meta": {"count": 1, "per_page": 50, "next_cursor": None},
            "results": [sample_openalex_work],
        }
        responses.add(responses.GET, f"{OPENALEX_BASE}/works", json=response, status=200)
        results = find_citing_works("W1234567890", email="test@example.com")
        assert len(results) == 0


class TestResolveDoi:
    @responses.activate
    def test_resolves_doi(self):
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works/https://doi.org/10.1038/s41593-019-0559-0",
            json={"id": "https://openalex.org/W2964321694"},
            status=200,
        )
        result = resolve_doi_to_openalex("10.1038/s41593-019-0559-0", email="test@example.com")
        assert result == "W2964321694"

    @responses.activate
    def test_unknown_doi_returns_none(self):
        responses.add(
            responses.GET,
            f"{OPENALEX_BASE}/works/https://doi.org/10.9999/nonexistent",
            json={"error": "not found"},
            status=404,
        )
        result = resolve_doi_to_openalex("10.9999/nonexistent", email="test@example.com")
        assert result is None
