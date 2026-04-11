# Citation Discovery System

Finds papers that are **meaningfully related** to your lab's tools -- papers that use them, extend them, build software for them, or review them -- by crawling citation graphs and analyzing full text with LLM sub-agents.

## Quick start

```bash
# 1. Edit discovery_config.yaml with your seed papers, tools, and email
# 2. Generate candidates (papers that cite your seed papers)
.venv/bin/python -m discovery.generate_candidates

# 3. Pre-fetch BibTeX and full text for all candidates
.venv/bin/python -m discovery.fulltext --stage candidates

# 4. Run the orchestrator to analyze all candidates
#    (in Claude Code, use the slash command)
/run-discovery --backlog

# 5. Review results in pipeline/reviewed/
#    Move approved ones to pipeline/approved/

# 6. Push approved citations into references.bib
.venv/bin/python -m discovery.approve
```

## How it works

### Pipeline stages

Each paper is a YAML file that moves through directories:

```
pipeline/candidates/   Papers identified from citation graphs, not yet analyzed
        │
        ▼  (pre-fetch: adds .bib and .txt companion files)
        │
        ▼
pipeline/in-progress/  Currently being analyzed by a sub-agent (gitignored)
        │
        ├──▶ pipeline/reviewed/    Related to tools — awaiting human review
        │
        └──▶ pipeline/rejected/    Not related (permanent record, prevents re-processing)

pipeline/approved/     Human verified — ready to sync to references.bib
```

To re-analyze a paper, move its YAML back to `candidates/`. The `stage_history` field preserves the full history of transitions.

### What counts as "related"

A paper is related if it does any of the following:
- **Uses** the tools for research (e.g., calcium imaging with Miniscope)
- **Extends or builds upon** the tools (hardware modifications, new variants)
- **Develops software** for the tools' data (e.g., Minian analysis pipeline)
- **Introduces** a tool in the project family (including your own lab's papers)
- **Reviews** the tools or their applications
- **Uses computational approaches** developed by the project

Papers are only rejected if they cite seed papers purely for scientific context with no connection to the tools (e.g., citing for memory engram concepts while doing electrophysiology).

### Candidate generation

The `generate_candidates` script queries the [OpenAlex API](https://docs.openalex.org/) to find all papers that cite each of your seed papers. It deduplicates against:

- Papers already in `references.bib`
- Papers already in any pipeline stage (including `rejected/`)
- The seed papers themselves

### Pre-fetching (BibTeX + full text)

The `fulltext` module fetches data before sub-agents run, so agents only need to read local files (no network permission issues):

```bash
# Pre-fetch all candidates
.venv/bin/python -m discovery.fulltext --stage candidates

# Pre-fetch specific files
.venv/bin/python -m discovery.fulltext pipeline/candidates/smith_2024_example.yaml
```

For each candidate YAML, this creates companion files:
- `{name}.bib` -- BibTeX from CrossRef (never LLM-generated)
- `{name}.txt` -- Full text from PMC, Unpaywall, or bioRxiv

Full text retrieval cascade:
1. **PubMed Central** -- Resolves PMCID via NCBI, fetches XML full text
2. **Unpaywall** -- Finds open-access versions via DOI lookup
3. **bioRxiv** -- Fetches JATS XML for preprints (DOI starts with 10.1101/)

Companion files are gitignored (re-fetchable) but YAML files are tracked.

### Per-citation analysis

The `/analyze-citation` skill runs as a Claude Code sub-agent on one YAML file. It:

1. Reads the YAML and companion `.txt`/`.bib` files
2. Checks for duplicates against `references.bib`
3. Searches full text for tool mentions with direct quotes as evidence
4. Scores confidence and categorizes the paper
5. Moves to `reviewed/` (related) or `rejected/` (unrelated)

### Orchestrator

The `/run-discovery` skill dispatches sub-agents in parallel batches of 5. It handles moving files, spawning agents, and reporting results.

### Approval

Move reviewed YAML files you approve to `pipeline/approved/`, then:

```bash
.venv/bin/python -m discovery.approve
```

This appends BibTeX entries (with component/technique fields from analysis) to `references.bib`. The existing GitHub Actions pipeline handles wiki sync.

## Configuration

All project-specific settings live in `discovery_config.yaml` at the repo root.

### `seed_papers`

Your lab's published tool papers. All papers citing these are checked as candidates.

```yaml
seed_papers:
  - doi: "10.1038/s41593-019-0559-0"
    short_name: "Shuman et al. 2019"
    openalex_id: null                   # resolved automatically on first run
```

### `tools`

What the LLM looks for in paper text. Includes both hardware and software tools. Each has a canonical name (maps to BibTeX `component` field) and aliases.

```yaml
tools:
  - name: "UCLA Miniscope v4"
    aliases: ["Miniscope v4", "open-source miniscope"]
    wiki_component: "UCLA Miniscope v4"
  - name: "Minian"
    aliases: ["MiniAn", "miniscope analysis pipeline"]
    wiki_component: "Minian"
```

### `search_keywords`

Supplemental PubMed keyword searches for papers that reference tools without citing a seed paper.

### `apis`

Email addresses for API polite pools. OpenAlex gives faster rate limits with email. Unpaywall requires email.

### `processing`

- `max_parallel_agents`: Sub-agents per batch (default: 5)
- `abstract_only_max_confidence`: Max confidence without full text (default: 0.5)

### `last_discovery_run`

Updated after each weekly run. Used by `--since-last-run` for incremental discovery.

## YAML file schema

| Section | Fields | Set when |
|---------|--------|----------|
| Identity | `doi`, `openalex_id`, `pmid`, `pmcid` | Candidate creation / pre-fetch |
| Metadata | `title`, `authors`, `journal`, `publication_year` | Candidate creation |
| Provenance | `source`, `seed_paper_doi`, `batch_id` | Candidate creation |
| BibTeX | `bibtex_raw`, `bibtex_source` | Pre-fetch (CrossRef) |
| Full text | `fulltext.source` | Pre-fetch |
| Analysis | `related_to_project`, `confidence`, `tools_identified`, `evidence`, `paper_type`, `reasoning` | Sub-agent analysis |
| Stage | `stage`, `stage_history` | Every transition |

### Paper types

- **science** -- Uses the tool for research
- **methods** -- Extends or builds upon the tool
- **software** -- Software/pipeline for the tool's data
- **tool_paper** -- Introduces a tool in the project family
- **review** -- Reviews the tool or its applications
- **unrelated** -- No connection to the tools (rejected)

## CLI reference

```bash
# Generate candidates (backlog)
python -m discovery.generate_candidates

# Generate candidates (weekly, since date)
python -m discovery.generate_candidates --since 2026-01-01
python -m discovery.generate_candidates --since-last-run

# Pre-fetch BibTeX and full text
python -m discovery.fulltext --stage candidates

# Approve reviewed citations into references.bib
python -m discovery.approve
```

### Claude Code skills

```
/run-discovery --backlog          # Full backlog processing
/run-discovery --since-last-run   # Weekly discovery
/analyze-citation example.yaml    # Analyze single citation
```

## Adapting for your own project

1. Clone this repo
2. Clear `references.bib`
3. Edit `discovery_config.yaml`:
   - Replace `seed_papers` with your tool papers' DOIs
   - Replace `tools` with your tool names and aliases
   - Replace `search_keywords` with relevant terms
   - Set your email in `apis`
4. Edit `config.json` to point at your wiki (or remove wiki sync)
5. `pip install -r requirements.txt`
6. Run `/run-discovery --backlog`

## Module reference

| Module | Purpose |
|--------|---------|
| `config.py` | Load and validate `discovery_config.yaml` |
| `openalex.py` | OpenAlex API -- citation graph queries, DOI resolution |
| `crossref.py` | BibTeX fetching via DOI content negotiation |
| `unpaywall.py` | Open-access PDF URL lookup |
| `fulltext.py` | Pre-fetch BibTeX + full text (PMC, Unpaywall, bioRxiv) |
| `candidates.py` | Candidate generation from OpenAlex + deduplication |
| `generate_candidates.py` | CLI entry point for candidate generation |
| `analysis.py` | YAML file I/O and pipeline stage transitions |
| `approve.py` | Approved citations → `references.bib` |

## Tests

```bash
.venv/bin/pytest tests/ -v
```

101 tests covering all modules. External API calls are mocked with the `responses` library. CI runs via `.github/workflows/test-discovery.yml`.
