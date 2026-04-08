#!/usr/bin/env python3
"""Generate a PR summary comment comparing .bib changes against the base branch.

Reads the current and base branch .bib files, compares entries, and writes
a markdown summary to a file (default: output/pr_summary.md).
"""

import os
import re

from bib_utils import (
    clean_latex,
    entry_changed,
    load_base_entries,
    load_bib_entries,
    load_config,
)


def format_entry_summary(entry):
    """Format a one-line summary of an entry."""
    authors = entry.get("author", "Unknown")
    first_author = clean_latex(re.split(r"\s+and\s+", authors)[0])
    year = entry.get("year", "????")
    title = clean_latex(entry.get("title", "Untitled"))
    if len(title) > 80:
        title = title[:77] + "..."
    return f"{first_author} ({year}) — {title}"


def generate_summary(base_entries, head_entries, keys_normalized, duplicates):
    """Generate markdown summary."""
    added = {k: v for k, v in head_entries.items() if k not in base_entries}
    removed = {k: v for k, v in base_entries.items() if k not in head_entries}
    edited = {}
    for key in head_entries:
        if key in base_entries and entry_changed(base_entries[key], head_entries[key]):
            edited[key] = head_entries[key]

    lines = ["## Citations Summary\n"]

    # Status badge
    has_issues = len(duplicates) > 0
    if has_issues:
        lines.append("> **Status:** :warning: Issues found\n")
    else:
        lines.append("> **Status:** :white_check_mark: All checks passed\n")

    # Stats
    lines.append(f"| Metric | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Total citations | {len(head_entries)} |")
    lines.append(f"| Added | {len(added)} |")
    lines.append(f"| Edited | {len(edited)} |")
    lines.append(f"| Removed | {len(removed)} |")
    lines.append(f"| Keys normalized | {keys_normalized} |")
    lines.append("")

    # Added
    if added:
        lines.append("<details>")
        lines.append(f"<summary><strong>Added ({len(added)})</strong></summary>\n")
        for key, entry in added.items():
            lines.append(f"- `{key}` — {format_entry_summary(entry)}")
        lines.append("\n</details>\n")

    # Edited
    if edited:
        lines.append("<details>")
        lines.append(f"<summary><strong>Edited ({len(edited)})</strong></summary>\n")
        for key, entry in edited.items():
            lines.append(f"- `{key}` — {format_entry_summary(entry)}")
        lines.append("\n</details>\n")

    # Removed
    if removed:
        lines.append("<details>")
        lines.append(f"<summary><strong>Removed ({len(removed)})</strong> — wiki pages will be deleted on merge</summary>\n")
        for key, entry in removed.items():
            lines.append(f"- `{key}` — {format_entry_summary(entry)}")
        lines.append("\n</details>\n")

    # Keys normalized
    if keys_normalized > 0:
        lines.append(f":wrench: **{keys_normalized} citation key(s)** were automatically normalized to the `author_year_firstword` format.\n")

    # Duplicates
    if duplicates:
        lines.append(":warning: **Potential duplicates found:**\n")
        for warning in duplicates:
            lines.append(f"```\n{warning}\n```\n")

    return "\n".join(lines)


def main():
    repo_root, config = load_config()

    base_ref = os.environ.get("BASE_REF", "origin/main")
    keys_normalized = int(os.environ.get("KEYS_NORMALIZED", "0"))
    duplicates_str = os.environ.get("DUPLICATES", "")
    duplicates = [d for d in duplicates_str.split("|||") if d.strip()] if duplicates_str else []

    # Load head (current) entries
    bib_paths = [repo_root / p for p in config["bib_files"]]
    head_entries = load_bib_entries(bib_paths)

    # Load base entries
    base_entries = load_base_entries(config["bib_files"], base_ref)

    summary = generate_summary(base_entries, head_entries, keys_normalized, duplicates)

    output_dir = repo_root / "output"
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / "pr_summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    print(summary)
    print(f"\nWritten to {summary_path}")


if __name__ == "__main__":
    main()
