"""Load and validate discovery_config.yaml."""

from pathlib import Path

import yaml


def load_discovery_config(config_path=None):
    """Load discovery config from YAML file.

    Args:
        config_path: Path to the YAML config file. If None, looks for
                     discovery_config.yaml in the repo root.

    Returns:
        Validated config dict.
    """
    if config_path is None:
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / "discovery_config.yaml"

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Discovery config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    validate_config(config)
    return config


def validate_config(config):
    """Validate required fields and fill in defaults.

    Raises ValueError if required fields are missing.
    """
    if not config.get("seed_papers"):
        raise ValueError("discovery_config.yaml must contain 'seed_papers' with at least one entry")

    if "tools" not in config:
        raise ValueError("discovery_config.yaml must contain 'tools'")

    for i, seed in enumerate(config["seed_papers"]):
        if not seed.get("doi"):
            raise ValueError(f"seed_papers[{i}] must have a 'doi' field")

    # Fill in defaults
    config.setdefault("search_keywords", [])
    config.setdefault("apis", {})
    config["apis"].setdefault("openalex_email", None)
    config["apis"].setdefault("unpaywall_email", None)
    config.setdefault("processing", {})
    config["processing"].setdefault("max_parallel_agents", 5)
    config["processing"].setdefault("abstract_only_max_confidence", 0.5)
    config.setdefault("last_discovery_run", None)
