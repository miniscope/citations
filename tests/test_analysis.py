"""Tests for discovery/analysis.py -- YAML I/O and stage transitions."""

import yaml
import pytest

from discovery.analysis import (
    load_citation,
    save_citation,
    move_to_stage,
    list_citations,
    get_existing_pipeline_dois,
)


class TestLoadSaveCitation:
    def test_roundtrip(self, pipeline_dirs, sample_candidate_data):
        path = pipeline_dirs["candidates"] / "zhang_2023_large.yaml"
        save_citation(path, sample_candidate_data)

        loaded = load_citation(path)
        assert loaded["doi"] == sample_candidate_data["doi"]
        assert loaded["title"] == sample_candidate_data["title"]
        assert loaded["stage"] == "candidate"
        assert len(loaded["authors"]) == 2

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_citation(tmp_path / "nonexistent.yaml")

    def test_preserves_none_values(self, pipeline_dirs, sample_candidate_data):
        path = pipeline_dirs["candidates"] / "test.yaml"
        save_citation(path, sample_candidate_data)
        loaded = load_citation(path)
        assert loaded["pmid"] is None
        assert loaded["bibtex_raw"] is None


class TestMoveToStage:
    def test_move_candidate_to_in_progress(self, pipeline_dirs, sample_candidate_data):
        src = pipeline_dirs["candidates"] / "test.yaml"
        save_citation(src, sample_candidate_data)

        move_to_stage("test.yaml", "in-progress", pipeline_root=pipeline_dirs["candidates"].parent)

        assert not src.exists()
        dest = pipeline_dirs["in-progress"] / "test.yaml"
        assert dest.exists()
        loaded = load_citation(dest)
        assert loaded["stage"] == "in-progress"
        assert len(loaded["stage_history"]) == 2

    def test_move_to_invalid_stage_raises(self, pipeline_dirs, sample_candidate_data):
        src = pipeline_dirs["candidates"] / "test.yaml"
        save_citation(src, sample_candidate_data)

        with pytest.raises(ValueError, match="Invalid stage"):
            move_to_stage("test.yaml", "invalid", pipeline_root=pipeline_dirs["candidates"].parent)

    def test_move_updates_stage_history(self, pipeline_dirs, sample_candidate_data):
        src = pipeline_dirs["candidates"] / "test.yaml"
        save_citation(src, sample_candidate_data)

        move_to_stage("test.yaml", "in-progress", pipeline_root=pipeline_dirs["candidates"].parent)
        move_to_stage("test.yaml", "reviewed", pipeline_root=pipeline_dirs["candidates"].parent)

        dest = pipeline_dirs["reviewed"] / "test.yaml"
        loaded = load_citation(dest)
        assert loaded["stage"] == "reviewed"
        assert len(loaded["stage_history"]) == 3


class TestListCitations:
    def test_empty_stage(self, pipeline_dirs):
        result = list_citations("candidates", pipeline_root=pipeline_dirs["candidates"].parent)
        assert result == []

    def test_lists_yaml_files(self, pipeline_dirs, sample_candidate_data):
        for name in ["a.yaml", "b.yaml", "c.yaml"]:
            save_citation(pipeline_dirs["candidates"] / name, sample_candidate_data)

        result = list_citations("candidates", pipeline_root=pipeline_dirs["candidates"].parent)
        assert len(result) == 3
        assert all(p.suffix == ".yaml" for p in result)

    def test_ignores_non_yaml(self, pipeline_dirs):
        (pipeline_dirs["candidates"] / ".gitkeep").touch()
        result = list_citations("candidates", pipeline_root=pipeline_dirs["candidates"].parent)
        assert result == []


class TestGetExistingPipelineDois:
    def test_collects_dois_across_stages(self, pipeline_dirs, sample_candidate_data):
        # Place one file in candidates, one in reviewed (different DOI)
        save_citation(pipeline_dirs["candidates"] / "a.yaml", sample_candidate_data)

        other = dict(sample_candidate_data)
        other["doi"] = "10.9999/other"
        save_citation(pipeline_dirs["reviewed"] / "b.yaml", other)

        dois = get_existing_pipeline_dois(pipeline_root=pipeline_dirs["candidates"].parent)
        assert "10.1038/s41467-023-39860-0" in dois
        assert "10.9999/other" in dois

    def test_skips_none_dois(self, pipeline_dirs, sample_candidate_data):
        no_doi = dict(sample_candidate_data)
        no_doi["doi"] = None
        save_citation(pipeline_dirs["candidates"] / "a.yaml", no_doi)

        dois = get_existing_pipeline_dois(pipeline_root=pipeline_dirs["candidates"].parent)
        assert len(dois) == 0
