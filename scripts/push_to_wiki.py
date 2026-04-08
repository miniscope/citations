#!/usr/bin/env python3
"""Push generated wikitext pages to a MediaWiki instance via the Action API.

Reads the manifest produced by bib_to_wikitext.py, logs in with bot credentials,
and creates/updates pages. Performs field-level merge: BibTeX fields always win,
but wiki-only fields added inside the template are preserved.
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
        resp = self.session.get(
            self.api_url,
            params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
        )
        login_token = resp.json()["query"]["tokens"]["logintoken"]

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


def parse_template_params(template_block):
    """Extract parameter key=value pairs from a {{TemplateName|...}} block."""
    params = {}
    for match in re.finditer(r"\|([^=|]+)=([^|]*?)(?=\n\||\n\}\}|\}\})", template_block, re.DOTALL):
        key = match.group(1).strip()
        value = match.group(2).strip()
        params[key] = value
    return params


def extract_template_blocks(content):
    """Extract the main Publication template and author subobject blocks from marker content."""
    # Get content between markers
    marker_match = re.search(
        re.escape(MARKER_START) + r"\n(.*?)\n" + re.escape(MARKER_END),
        content, re.DOTALL,
    )
    if not marker_match:
        return None, []

    inner = marker_match.group(1)

    # Find main Publication template (not the subobject ones)
    main_match = re.search(r"\{\{Publication\n(.*?)\}\}", inner, re.DOTALL)
    main_block = main_match.group(0) if main_match else None

    # Find all author subobject blocks
    author_blocks = re.findall(
        r"\{\{Publication Has publication author\n.*?\}\}", inner, re.DOTALL
    )

    return main_block, author_blocks


def build_template_call(name, params):
    """Rebuild a template call from a name and ordered params dict."""
    lines = ["{{" + name]
    for key, value in params.items():
        if value:
            lines.append(f"|{key}={value}")
    lines.append("}}")
    return "\n".join(lines)


def merge_with_existing(new_content, existing_content):
    """Merge new BibTeX content with existing wiki page content.

    Strategy:
    - Content outside markers is always preserved from existing page
    - Main Publication template: BibTeX fields override, wiki-only fields preserved
    - Author subobjects: always replaced from BibTeX (authoritative source)
    """
    if existing_content is None:
        return new_content

    marker_pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )

    # If existing page has no markers, just use new content
    if not marker_pattern.search(existing_content):
        return new_content

    # Extract template data from both
    existing_main, _ = extract_template_blocks(existing_content)
    new_main, new_author_blocks = extract_template_blocks(new_content)

    if not new_main:
        return new_content

    # Merge main template params: start with existing, overlay with new
    existing_params = parse_template_params(existing_main) if existing_main else {}
    new_params = parse_template_params(new_main)

    merged_params = {}
    # Preserve existing wiki-only fields
    for key, value in existing_params.items():
        merged_params[key] = value
    # BibTeX fields always win
    for key, value in new_params.items():
        merged_params[key] = value

    # Rebuild marker block
    merged_main = build_template_call("Publication", merged_params)
    marker_content = merged_main
    if new_author_blocks:
        marker_content += "\n\n" + "\n\n".join(new_author_blocks)

    new_marker_block = f"{MARKER_START}\n{marker_content}\n{MARKER_END}"

    # Replace marker block in existing page, preserving everything outside
    return marker_pattern.sub(new_marker_block, existing_content)


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
