"""OpenAlex API client for citation graph queries."""

import re

import requests

OPENALEX_BASE = "https://api.openalex.org"


def parse_openalex_work(work):
    """Convert an OpenAlex work object to a normalized candidate dict.

    Extracts the fields we care about from the OpenAlex API response format.
    """
    raw_doi = work.get("doi")
    doi = re.sub(r"^https?://doi\.org/", "", raw_doi) if raw_doi else None

    raw_id = work.get("id", "")
    openalex_id = raw_id.replace("https://openalex.org/", "") if raw_id else None

    # Parse authors
    authors = []
    for authorship in work.get("authorships", []):
        display_name = authorship.get("author", {}).get("display_name", "")
        parts = display_name.rsplit(" ", 1)
        if len(parts) == 2:
            authors.append({"first": parts[0], "last": parts[1]})
        elif parts:
            authors.append({"first": "", "last": parts[0]})

    # Parse journal from primary_location
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    journal = source.get("display_name")

    # Open access info
    oa = work.get("open_access", {})
    open_access = {
        "is_oa": oa.get("is_oa", False),
        "oa_url": oa.get("oa_url"),
    }

    return {
        "doi": doi,
        "openalex_id": openalex_id,
        "pmid": None,
        "pmcid": None,
        "title": work.get("title"),
        "authors": authors,
        "journal": journal,
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "is_retracted": work.get("is_retracted", False),
        "open_access": open_access,
    }


def find_citing_works(openalex_id, email=None, from_date=None, to_date=None):
    """Find all works that cite a given OpenAlex work.

    Uses cursor-based pagination to retrieve all results.
    Filters out retracted papers.

    Args:
        openalex_id: OpenAlex Work ID (e.g., "W1234567890")
        email: Email for polite pool (faster rate limits)
        from_date: Optional start date filter (YYYY-MM-DD)
        to_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        List of parsed work dicts.
    """
    results = []
    cursor = "*"

    while cursor:
        filter_parts = [f"cites:{openalex_id}"]
        if from_date:
            filter_parts.append(f"from_publication_date:{from_date}")
        if to_date:
            filter_parts.append(f"to_publication_date:{to_date}")

        params = {
            "filter": ",".join(filter_parts),
            "per-page": 50,
            "cursor": cursor,
            "select": "id,doi,title,publication_date,publication_year,authorships,"
                      "type,is_retracted,open_access,primary_location",
        }
        if email:
            params["mailto"] = email

        try:
            resp = requests.get(f"{OPENALEX_BASE}/works", params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            break

        data = resp.json()
        for work in data.get("results", []):
            parsed = parse_openalex_work(work)
            if not parsed["is_retracted"]:
                results.append(parsed)

        cursor = data.get("meta", {}).get("next_cursor")

    return results


def resolve_doi_to_openalex(doi, email=None):
    """Look up a DOI and return its OpenAlex Work ID.

    Returns None if the DOI is not found.
    """
    url = f"{OPENALEX_BASE}/works/https://doi.org/{doi}"
    params = {}
    if email:
        params["mailto"] = email

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except requests.RequestException:
        return None

    data = resp.json()
    raw_id = data.get("id", "")
    return raw_id.replace("https://openalex.org/", "") if raw_id else None
