"""Unpaywall API client for finding open-access PDF URLs."""

import requests

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


def find_oa_pdf(doi, email):
    """Look up open-access PDF availability for a DOI via Unpaywall.

    Args:
        doi: The DOI to look up (without https://doi.org/ prefix).
        email: Required by Unpaywall API for identification.

    Returns:
        Dict with 'url', 'url_for_pdf', and 'host_type' keys if an OA
        version is found. Returns None if no OA version exists.
    """
    url = f"{UNPAYWALL_BASE}/{doi}"
    params = {"email": email}

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    data = resp.json()
    best = data.get("best_oa_location")
    if not best:
        return None

    return {
        "url": best.get("url"),
        "url_for_pdf": best.get("url_for_pdf"),
        "host_type": best.get("host_type"),
    }
