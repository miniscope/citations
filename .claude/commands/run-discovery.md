Orchestrate the citation discovery pipeline. Mode: $ARGUMENTS

If $ARGUMENTS is empty or "--backlog", run in backlog mode (all citations).
If $ARGUMENTS is "--since YYYY-MM-DD", run in weekly mode since that date.
If $ARGUMENTS is "--since-last-run", use the date from discovery_config.yaml.
If $ARGUMENTS is "--continue", skip candidate generation and pre-fetch, resume analyzing existing candidates.

## Phase 1: Generate candidates

```bash
cd /home/daharoni/dev/citations
.venv/bin/python -m discovery.generate_candidates $ARGUMENTS
```

## Phase 2: Pre-fetch BibTeX and full text

```bash
.venv/bin/python -m discovery.fulltext --stage candidates
```

This creates companion .bib and .txt files alongside each candidate YAML.
Sub-agents will read these local files instead of making network calls.

## Phase 3: Check candidate count

```bash
ls pipeline/candidates/*.yaml 2>/dev/null | wc -l
```

If zero: report "No new candidates found" and stop.
If more than 200 (backlog): tell the user how many and confirm before proceeding.

## Phase 4: Process candidates in batches of 5

For each batch:

### 4a. Move candidates with companion files to in-progress

```bash
for f in $(ls pipeline/candidates/*.yaml | head -5); do
  base=$(basename "$f" .yaml)
  mv "$f" pipeline/in-progress/
  [ -f "pipeline/candidates/$base.txt" ] && mv "pipeline/candidates/$base.txt" pipeline/in-progress/
  [ -f "pipeline/candidates/$base.bib" ] && mv "pipeline/candidates/$base.bib" pipeline/in-progress/
done
```

### 4b. Dispatch 5 sub-agents in parallel

For each YAML file in pipeline/in-progress/, spawn a background Agent with this prompt:

```
Analyze one citation candidate in /home/daharoni/dev/citations.

Process: pipeline/in-progress/{filename}

## Scope
A paper is related if it: uses the tools for research, extends/builds upon them,
introduces a tool in the family, develops software for the tools' data, or reviews them.
ONLY reject if it cites seed papers purely for scientific context with NO tool connection.
Do NOT reject papers from the tool developers' lab.

## Steps
1. Read the YAML, companion .txt file (pre-fetched full text), and .bib file
   (pre-fetched BibTeX). Read discovery_config.yaml for the tools list.
2. Check if DOI exists in references.bib -- if duplicate, reject.
3. Store .bib contents in bibtex_raw, set bibtex_source: "crossref".
4. Search the .txt full text for tool mentions. Tools: UCLA Miniscope v4, MiniLFOV,
   MiniXL, Minian, UCLA 2P Miniscope, Miniscope DAQ (check all aliases in config).
5. Set: related_to_project (true/false), confidence (0-1),
   paper_type (science|methods|software|tool_paper|review|unrelated),
   suggested_component, suggested_technique, reasoning, evidence (direct quotes only).
6. If related → move YAML to pipeline/reviewed/. If not → pipeline/rejected/.
7. Print: RESULT: {filename} | related={t/f} | type={type} | confidence={0.XX}
```

Launch all 5 agents in a single message using run_in_background: true.

### 4c. After batch completes, check results and continue

```bash
echo "Candidates: $(ls pipeline/candidates/*.yaml 2>/dev/null | wc -l)"
echo "Reviewed: $(ls pipeline/reviewed/*.yaml 2>/dev/null | wc -l)"
echo "Rejected: $(ls pipeline/rejected/*.yaml 2>/dev/null | wc -l)"
```

If more candidates remain, repeat from 4a.

## Phase 5: Handle stuck files

```bash
ls pipeline/in-progress/*.yaml 2>/dev/null
```

If any files stuck in in-progress, move back to candidates and retry.

## Phase 6: Summary report

```
=== Discovery Run Complete ===
Candidates processed: N
Related to project (reviewed): N
Not related (rejected): N
Remaining: N
```

## Phase 7: Update last run date

If weekly/--since mode, update `last_discovery_run` in discovery_config.yaml.
