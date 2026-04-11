#!/usr/bin/env python3
"""CLI entry point for generating citation candidates.

Usage:
    # Backlog mode (all citations, no date filter)
    python -m discovery.generate_candidates

    # Weekly mode (since a specific date)
    python -m discovery.generate_candidates --since 2026-04-01

    # Weekly mode (since last recorded run)
    python -m discovery.generate_candidates --since-last-run
"""

import argparse
import sys
from pathlib import Path

from discovery.candidates import generate_candidates
from discovery.config import load_discovery_config


def main():
    parser = argparse.ArgumentParser(description="Generate citation candidates")
    parser.add_argument(
        "--since",
        help="Only find papers published after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--since-last-run",
        action="store_true",
        help="Only find papers published after the last discovery run",
    )
    parser.add_argument(
        "--config",
        help="Path to discovery_config.yaml (default: repo root)",
    )
    args = parser.parse_args()

    from_date = args.since
    if args.since_last_run:
        config = load_discovery_config(args.config)
        from_date = config.get("last_discovery_run")
        if not from_date:
            print("No last_discovery_run date found in config. Running full backlog.")

    files = generate_candidates(
        config_path=args.config,
        from_date=from_date,
    )

    print(f"\nGenerated {len(files)} candidate(s) in pipeline/candidates/")
    for f in files[:10]:
        print(f"  {f.name}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")


if __name__ == "__main__":
    main()
