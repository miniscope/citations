Analyze ONE citation candidate to determine whether the paper is meaningfully
related to the lab's tools. Process the file: $ARGUMENTS

## Scope -- what counts as related

A paper is related if it does ANY of the following:
- **Uses** the tools for research (e.g., "We used the UCLA Miniscope v4 to image...")
- **Extends or builds upon** the tools (e.g., software pipelines, hardware modifications)
- **Introduces** a tool in the project family (seed papers, new variants)
- **Reviews** the tools or their applications

A paper should ONLY be rejected if it cites the seed papers purely for
scientific context with NO connection to the tools themselves (e.g., citing
Cai et al. 2016 for memory engram concepts while doing electrophysiology).

Do NOT reject papers just because they are from the tool developers' lab.
Do NOT reject seed papers or papers that describe/introduce tools in the project.

## Steps

### 1. Read inputs

Read the candidate YAML file and its companion files (if they exist):
- `pipeline/in-progress/$ARGUMENTS` -- the YAML metadata
- `pipeline/in-progress/{name}.txt` -- pre-fetched full text (if available)
- `pipeline/in-progress/{name}.bib` -- pre-fetched BibTeX (if available)

Also read `discovery_config.yaml` to get the list of tools and their aliases.

### 2. Check for duplicates

Check if this paper's DOI already exists in `references.bib`. If it does,
mark the YAML with `analysis.status: "duplicate"` and move to
`pipeline/rejected/`. Stop here.

### 3. Read full text

If a companion `.txt` file exists, read it -- this is the pre-fetched full text.
If no `.txt` file exists, try these fallbacks in order:
- PubMed MCP `get_full_text_article` if PMCID is available
- bioRxiv MCP `get_preprint` if DOI starts with 10.1101/
- Otherwise proceed with abstract/title only

### 4. Read BibTeX

If a companion `.bib` file exists, read it and store in `bibtex_raw`.
Set `bibtex_source: "crossref"`.
If no `.bib` file exists, try:
```bash
curl -sL -H "Accept: application/x-bibtex" "https://doi.org/{doi}"
```
Store the EXACT response. Do NOT write BibTeX yourself.

### 5. Analyze for tool relevance

Search the full text (or abstract if no full text) for evidence that the paper
is related to the project's tools.

**Paper types to ACCEPT (move to reviewed/):**
- `science` -- Uses the tool for research experiments
- `methods` -- Extends, modifies, or builds upon the tool
- `software` -- Software/analysis pipeline for the tool's data
- `tool_paper` -- Introduces or describes a tool in the project family
- `review` -- Reviews the tool or its applications

**Papers to REJECT (move to rejected/):**
- `unrelated` -- Cites seed papers only for scientific context, no tool connection

For each tool found, record:
- Which tool (canonical name from config)
- Confidence (0.0-1.0)
- The section where evidence was found
- Direct quotes as evidence (EXACT text from the paper, not paraphrased)

Set these fields:
- `related_to_project`: true/false
- `confidence`: 0.0 to 1.0 (cap at 0.5 if abstract-only for science papers)
- `paper_type`: "science" | "methods" | "software" | "tool_paper" | "review" | "unrelated"
- `suggested_component`: comma-separated tool names for BibTeX component field
- `suggested_technique`: e.g. "Calcium Imaging"
- `reasoning`: 2-3 sentence explanation

**CRITICAL: Evidence MUST be direct quotes, never paraphrased.**

### 6. Write results and move file

Update all fields in the YAML file.

If `related_to_project` is false, move to `pipeline/rejected/`.
Otherwise, move to `pipeline/reviewed/`.

```bash
mv "pipeline/in-progress/$ARGUMENTS" "pipeline/{reviewed or rejected}/$ARGUMENTS"
```

Update `stage` and `stage_history` accordingly.

### 7. Print summary

```
RESULT: {filename} | related={true/false} | type={paper_type} | confidence={0.XX} | tools={list} | fulltext={source}
```
