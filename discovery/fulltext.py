"""Pre-fetch full text and BibTeX for citation candidates.

Separates data fetching (needs network) from analysis (needs only local files).
Run this before dispatching sub-agents so they only need Read permission.

Each candidate YAML file gets companion files saved alongside it:
  - {name}.bib  -- BibTeX from CrossRef
  - {name}.txt  -- Full text (from PMC, Unpaywall, or bioRxiv)

Usage:
    # Pre-fetch all candidates
    python -m discovery.fulltext

    # Pre-fetch specific files
    python -m discovery.fulltext pipeline/candidates/smith_2024_example.yaml
"""

import re
import sys
import time
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def fetch_and_save_bibtex(yaml_path):
    """Fetch BibTeX from CrossRef for a candidate and save as companion .bib file.

    Also updates the YAML file with bibtex_raw and bibtex_source fields.
    Returns the path to the .bib file, or None if fetching failed.
    """
    yaml_path = Path(yaml_path)
    data = yaml.safe_load(yaml_path.read_text())
    doi = data.get("doi")
    if not doi:
        return None

    # Fetch from CrossRef via content negotiation
    try:
        resp = requests.get(
            f"https://doi.org/{doi}",
            headers={"Accept": "application/x-bibtex"},
            timeout=30,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        bibtex = resp.text
    except (requests.RequestException, ConnectionError):
        return None

    if not bibtex or "@" not in bibtex:
        return None

    # Save companion .bib file
    bib_path = yaml_path.with_suffix(".bib")
    bib_path.write_text(bibtex, encoding="utf-8")

    # Update YAML
    data["bibtex_raw"] = bibtex
    data["bibtex_source"] = "crossref"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return bib_path


def _strip_html(html):
    """Crude HTML tag removal for extracting readable text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_pmc_fulltext(pmcid):
    """Fetch full text from PubMed Central via the OA web service."""
    if not pmcid:
        return None
    # Use NCBI E-utilities to get full text XML
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pmc", "id": pmcid, "rettype": "xml"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 500:
            # Strip XML tags to get readable text
            return _strip_html(resp.text)
    except (requests.RequestException, ConnectionError):
        pass
    return None


def _resolve_pmcid(doi):
    """Try to resolve a DOI to a PMCID via NCBI ID converter."""
    url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    params = {"ids": doi, "format": "json"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("records", [])
            if records and records[0].get("pmcid"):
                return records[0]["pmcid"]
    except (requests.RequestException, ConnectionError, ValueError):
        pass
    return None


def _fetch_unpaywall_text(doi, email):
    """Find OA full text via Unpaywall and fetch it."""
    try:
        resp = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": email},
            timeout=15,
        )
        if resp.status_code != 200:
            return None, None
        data = resp.json()
    except (requests.RequestException, ConnectionError, ValueError):
        return None, None

    best = data.get("best_oa_location")
    if not best:
        return None, None

    # Prefer HTML page over PDF (easier to extract text)
    url = best.get("url") or best.get("url_for_pdf")
    if not url:
        return None, None

    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "CitationDiscovery/1.0"})
        if resp.status_code == 200 and len(resp.text) > 100:
            text = _strip_html(resp.text)
            if len(text) > 50:
                return text, "unpaywall"
    except (requests.RequestException, ConnectionError):
        pass

    return None, None


def _fetch_biorxiv_text(doi):
    """Fetch bioRxiv preprint text via the JATS XML endpoint."""
    if not doi or not doi.startswith("10.1101/"):
        return None
    # bioRxiv provides JATS XML at a predictable URL
    xml_url = f"https://www.biorxiv.org/content/{doi}v1.source.xml"
    try:
        resp = requests.get(xml_url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 500:
            return _strip_html(resp.text)
    except (requests.RequestException, ConnectionError):
        pass
    return None


def fetch_and_save_fulltext(yaml_path, email=None):
    """Fetch full text for a candidate and save as companion .txt file.

    Tries sources in order: PMC > Unpaywall > bioRxiv.
    Updates the YAML with fulltext.source.
    Returns path to .txt file, or None if no full text available.
    """
    yaml_path = Path(yaml_path)
    data = yaml.safe_load(yaml_path.read_text())
    doi = data.get("doi")
    pmcid = data.get("pmcid")

    text = None
    source = None

    # 1. Try PMC (resolve PMCID if needed)
    if not pmcid and doi:
        pmcid = _resolve_pmcid(doi)
        if pmcid:
            data["pmcid"] = pmcid

    if pmcid:
        text = _fetch_pmc_fulltext(pmcid)
        if text:
            source = "pmc"

    # 2. Try Unpaywall
    if not text and doi and email:
        text, source = _fetch_unpaywall_text(doi, email)

    # 3. Try bioRxiv
    if not text and doi:
        text = _fetch_biorxiv_text(doi)
        if text:
            source = "biorxiv"

    if not text:
        return None

    # Save companion .txt file
    txt_path = yaml_path.with_suffix(".txt")
    txt_path.write_text(text, encoding="utf-8")

    # Update YAML
    data["fulltext"]["source"] = source
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return txt_path


def prefetch_candidate(yaml_path, email=None):
    """Pre-fetch both BibTeX and full text for a single candidate.

    Returns (bib_path, txt_path) -- either may be None.
    """
    bib_path = fetch_and_save_bibtex(yaml_path)
    txt_path = fetch_and_save_fulltext(yaml_path, email=email)
    return bib_path, txt_path


def main():
    """Pre-fetch full text and BibTeX for candidates."""
    import argparse

    parser = argparse.ArgumentParser(description="Pre-fetch full text and BibTeX")
    parser.add_argument("files", nargs="*", help="Specific YAML files to process")
    parser.add_argument("--email", help="Email for Unpaywall API")
    parser.add_argument("--stage", default="candidates",
                        help="Pipeline stage to process (default: candidates)")
    args = parser.parse_args()

    # Load email from config if not provided
    if not args.email:
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / "discovery_config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            args.email = config.get("apis", {}).get("unpaywall_email")

    if args.files:
        yaml_files = [Path(f) for f in args.files]
    else:
        repo_root = Path(__file__).resolve().parent.parent
        stage_dir = repo_root / "pipeline" / args.stage
        yaml_files = sorted(stage_dir.glob("*.yaml"))

    stats = {"bibtex": 0, "fulltext": 0, "total": 0}
    for yaml_path in yaml_files:
        stats["total"] += 1
        print(f"  [{stats['total']}/{len(yaml_files)}] {yaml_path.name}...", end=" ", flush=True)

        bib_path, txt_path = prefetch_candidate(yaml_path, email=args.email)

        parts = []
        if bib_path:
            stats["bibtex"] += 1
            parts.append("bib")
        if txt_path:
            stats["fulltext"] += 1
            parts.append(f"txt ({yaml.safe_load(yaml_path.read_text())['fulltext']['source']})")
        print(", ".join(parts) if parts else "no data available")

        # Rate limiting: be polite to APIs
        time.sleep(0.5)

    print(f"\nDone: {stats['total']} processed, "
          f"{stats['bibtex']} BibTeX fetched, "
          f"{stats['fulltext']} full text fetched")


if __name__ == "__main__":
    main()
