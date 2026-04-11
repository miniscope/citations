"""YAML I/O and pipeline stage management for citation files."""

from datetime import datetime, timezone
from pathlib import Path

import yaml

VALID_STAGES = {"candidates", "in-progress", "reviewed", "approved", "rejected"}


def _get_default_pipeline_root():
    """Get the default pipeline root directory."""
    return Path(__file__).resolve().parent.parent / "pipeline"


def load_citation(filepath):
    """Read a citation YAML file and return its data as a dict."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Citation file not found: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_citation(filepath, data):
    """Write a citation data dict to a YAML file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def move_to_stage(filename, new_stage, pipeline_root=None):
    """Move a citation YAML file to a new pipeline stage directory.

    Finds the file in its current stage, updates the stage field and
    stage_history, then moves it to the new stage directory.
    """
    if new_stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage '{new_stage}'. Must be one of: {VALID_STAGES}")

    if pipeline_root is None:
        pipeline_root = _get_default_pipeline_root()
    pipeline_root = Path(pipeline_root)

    # Find the file in any current stage
    src = None
    for stage in VALID_STAGES:
        candidate = pipeline_root / stage / filename
        if candidate.exists():
            src = candidate
            break

    if src is None:
        raise FileNotFoundError(f"Citation file '{filename}' not found in any pipeline stage")

    data = load_citation(src)
    data["stage"] = new_stage
    data.setdefault("stage_history", [])
    data["stage_history"].append({
        "stage": new_stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    dest = pipeline_root / new_stage / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_citation(dest, data)
    src.unlink()


def list_citations(stage, pipeline_root=None):
    """List all YAML files in a given pipeline stage directory."""
    if pipeline_root is None:
        pipeline_root = _get_default_pipeline_root()
    pipeline_root = Path(pipeline_root)

    stage_dir = pipeline_root / stage
    if not stage_dir.exists():
        return []
    return sorted(p for p in stage_dir.iterdir() if p.suffix == ".yaml")


def get_existing_pipeline_dois(pipeline_root=None):
    """Collect all DOIs from YAML files across all pipeline stages."""
    if pipeline_root is None:
        pipeline_root = _get_default_pipeline_root()

    dois = set()
    for stage in VALID_STAGES:
        for filepath in list_citations(stage, pipeline_root):
            data = load_citation(filepath)
            doi = data.get("doi")
            if doi:
                dois.add(doi)
    return dois
