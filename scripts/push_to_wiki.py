#!/usr/bin/env python3
"""Push generated wikitext pages to a MediaWiki instance via the Action API.

Reads the manifest produced by bib_to_wikitext.py, logs in with bot credentials,
and creates/updates pages. Uses markers to preserve manual edits outside the
synced region.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

MARKER_START = "<!-- citations-sync start -->"
MARKER_END = "<!-- citations-sync end -->"


def get_credentials():
    """Read wiki credentials from environment variables."""
    api_url = os.environ.get("WIKI_API_URL")
    username = os.environ.get("WIKI_BOT_USERNAME")
    password = os.environ.get("WIKI_BOT_PASSWORD")
    if not all([api_url, username, password]):
        print(
            "Error: set WIKI_API_URL, WIKI_BOT_USERNAME, WIKI_BOT_PASSWORD",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_url, username, password


class WikiClient:
    """Minimal MediaWiki API client for page editing."""

    def __init__(self, api_url):
        self.api_url = api_url
        self.session = requests.Session()

    def login(self, username, password):
        """Log in via the MediaWiki Action API."""
        # Get login token
        resp = self.session.get(
            self.api_url,
            params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
        )
        login_token = resp.json()["query"]["tokens"]["logintoken"]

        # Log in
        resp = self.session.post(
            self.api_url,
            data={
                "action": "login",
                "lgname": username,
                "lgpassword": password,
                "lgtoken": login_token,
                "format": "json",
            },
        )
        result = resp.json()["login"]["result"]
        if result != "Success":
            print(f"Login failed: {result}", file=sys.stderr)
            sys.exit(1)

    def get_csrf_token(self):
        resp = self.session.get(
            self.api_url,
            params={"action": "query", "meta": "tokens", "format": "json"},
        )
        return resp.json()["query"]["tokens"]["csrftoken"]

    def get_page_content(self, title):
        """Fetch current page content, or None if the page doesn't exist."""
        resp = self.session.get(
            self.api_url,
            params={
                "action": "query",
                "titles": title,
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
            },
        )
        pages = resp.json()["query"]["pages"]
        for page_id, page_data in pages.items():
            if page_id == "-1":
                return None
            revisions = page_data.get("revisions", [])
            if revisions:
                return revisions[0]["slots"]["main"]["*"]
        return None

    def edit_page(self, title, content, summary, csrf_token):
        """Create or update a wiki page."""
        resp = self.session.post(
            self.api_url,
            data={
                "action": "edit",
                "title": title,
                "text": content,
                "summary": summary,
                "bot": "1",
                "token": csrf_token,
                "format": "json",
            },
        )
        result = resp.json()
        if "error" in result:
            return False, result["error"]["info"]
        edit_info = result.get("edit", {})
        return True, edit_info.get("result", "Unknown")


def merge_with_existing(new_content, existing_content):
    """Replace content between markers in existing page, preserving the rest.

    If existing page has no markers, return new_content as-is.
    """
    if existing_content is None:
        return new_content

    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )

    if pattern.search(existing_content):
        # Extract new marker block from new_content
        new_match = pattern.search(new_content)
        if new_match:
            return pattern.sub(new_match.group(), existing_content)

    return new_content


def main():
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = repo_root / "output"
    manifest_path = output_dir / "manifest.json"

    if not manifest_path.exists():
        print("Error: run bib_to_wikitext.py first to generate output/", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    if not manifest:
        print("No entries to push.")
        return

    api_url, username, password = get_credentials()
    client = WikiClient(api_url)
    client.login(username, password)
    csrf_token = client.get_csrf_token()

    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for key, info in manifest.items():
        title = info["page_title"]
        wikitext_path = output_dir / info["file"]
        new_content = wikitext_path.read_text(encoding="utf-8")

        existing = client.get_page_content(title)
        final_content = merge_with_existing(new_content, existing)

        if existing is not None and final_content == existing:
            skipped += 1
            continue

        success, result = client.edit_page(
            title, final_content, "citations-sync: update from BibTeX", csrf_token
        )
        if success:
            if existing is None:
                created += 1
                print(f"  + {title}")
            else:
                updated += 1
                print(f"  ~ {title}")
        else:
            errors += 1
            print(f"  ! {title}: {result}", file=sys.stderr)

    print(f"\nDone: {created} created, {updated} updated, {skipped} unchanged, {errors} errors")


if __name__ == "__main__":
    main()
