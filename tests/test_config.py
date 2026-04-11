"""Tests for discovery/config.py -- discovery configuration loader."""

import yaml
import pytest

from discovery.config import load_discovery_config, validate_config


class TestLoadDiscoveryConfig:
    def test_loads_valid_config(self, sample_discovery_config):
        config = load_discovery_config(sample_discovery_config)
        assert "seed_papers" in config
        assert "tools" in config
        assert len(config["seed_papers"]) == 1
        assert config["seed_papers"][0]["doi"] == "10.1038/s41593-019-0559-0"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_discovery_config(tmp_path / "nonexistent.yaml")

    def test_missing_seed_papers_raises(self, tmp_path):
        config_path = tmp_path / "discovery_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"tools": [], "search_keywords": []}, f)
        with pytest.raises(ValueError, match="seed_papers"):
            load_discovery_config(config_path)

    def test_missing_tools_raises(self, tmp_path):
        config_path = tmp_path / "discovery_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"seed_papers": [{"doi": "10.1234/test"}]}, f)
        with pytest.raises(ValueError, match="tools"):
            load_discovery_config(config_path)

    def test_seed_paper_without_doi_raises(self, tmp_path):
        config_path = tmp_path / "discovery_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({
                "seed_papers": [{"short_name": "No DOI"}],
                "tools": [{"name": "Tool", "aliases": []}],
            }, f)
        with pytest.raises(ValueError, match="doi"):
            load_discovery_config(config_path)


class TestValidateConfig:
    def test_valid_minimal_config(self):
        config = {
            "seed_papers": [{"doi": "10.1234/test", "short_name": "Test"}],
            "tools": [{"name": "My Tool", "aliases": ["tool"]}],
        }
        validate_config(config)  # should not raise

    def test_defaults_filled_in(self):
        config = {
            "seed_papers": [{"doi": "10.1234/test"}],
            "tools": [{"name": "My Tool", "aliases": []}],
        }
        validate_config(config)
        assert "apis" in config
        assert "processing" in config
        assert config["processing"]["max_parallel_agents"] == 5
        assert config["processing"]["abstract_only_max_confidence"] == 0.5
