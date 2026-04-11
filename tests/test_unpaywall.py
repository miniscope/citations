"""Tests for discovery/unpaywall.py -- Open access PDF URL lookup."""

import pytest
import responses

from discovery.unpaywall import find_oa_pdf

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


class TestFindOaPdf:
    @responses.activate
    def test_finds_oa_pdf(self):
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.1038/s41467-023-39860-0",
            json={
                "doi": "10.1038/s41467-023-39860-0",
                "is_oa": True,
                "best_oa_location": {
                    "url": "https://www.nature.com/articles/s41467-023-39860-0",
                    "url_for_pdf": "https://www.nature.com/articles/s41467-023-39860-0.pdf",
                    "host_type": "publisher",
                },
            },
            status=200,
        )
        result = find_oa_pdf("10.1038/s41467-023-39860-0", email="test@example.com")
        assert result is not None
        assert result["url_for_pdf"].endswith(".pdf")
        assert result["host_type"] == "publisher"

    @responses.activate
    def test_no_oa_available(self):
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.9999/paywalled",
            json={
                "doi": "10.9999/paywalled",
                "is_oa": False,
                "best_oa_location": None,
            },
            status=200,
        )
        result = find_oa_pdf("10.9999/paywalled", email="test@example.com")
        assert result is None

    @responses.activate
    def test_unknown_doi_returns_none(self):
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.9999/nonexistent",
            json={"error": "not found"},
            status=404,
        )
        result = find_oa_pdf("10.9999/nonexistent", email="test@example.com")
        assert result is None

    @responses.activate
    def test_sends_email_param(self):
        responses.add(
            responses.GET,
            f"{UNPAYWALL_BASE}/10.1234/test",
            json={"is_oa": False, "best_oa_location": None},
            status=200,
        )
        find_oa_pdf("10.1234/test", email="myemail@example.com")
        assert "email=myemail" in responses.calls[0].request.url
