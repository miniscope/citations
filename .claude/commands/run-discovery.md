Orchestrate the citation discovery pipeline. Mode: $ARGUMENTS

If $ARGUMENTS is empty or "--backlog", run in backlog mode (all citations).
If $ARGUMENTS is "--since YYYY-MM-DD", run in weekly mode since that date.
If $ARGUMENTS is "--since-last-run", use the date from discovery_config.yaml.

## Phase 1: Generate candidates

Run the candidate generation script:
```bash
cd /home/daharoni/dev/citations
.venv/bin/python -m discovery.generate_candidates $ARGUMENTS
```

This creates YAML files in `pipeline/candidates/`.

## Phase 2: Check candidate count

```bash
ls pipeline/candidates/*.yaml 2>/dev/null | wc -l
```

If zero candidates: report "No new candidates found" and stop.
If more than 200 candidates (backlog mode): tell the user how many were found
and confirm before proceeding.

## Phase 3: Process candidates in batches

For each batch:

1. Move up to 5 candidates to in-progress:
```bash
for f in $(ls pipeline/candidates/*.yaml 2>/dev/null | head -5); do
  mv "$f" pipeline/in-progress/
done
```

2. For each file now in `pipeline/in-progress/`, spawn a sub-agent using the
   Agent tool with the analyze-citation skill:

```
Agent({
  description: "Analyze citation: {filename}",
  prompt: "/analyze-citation {filename}"
})
```

Launch up to 5 sub-agents in parallel (all in a single message with multiple
Agent tool calls).

3. After the batch completes, check results:
```bash
echo "Reviewed:"; ls pipeline/reviewed/*.yaml 2>/dev/null | wc -l
echo "Rejected:"; ls pipeline/rejected/*.yaml 2>/dev/null | wc -l
echo "Remaining:"; ls pipeline/candidates/*.yaml 2>/dev/null | wc -l
```

4. If more candidates remain in `pipeline/candidates/`, repeat from step 1.

## Phase 4: Handle stuck files

After all batches, check if any files are stuck in in-progress:
```bash
ls pipeline/in-progress/*.yaml 2>/dev/null
```
If any exist, attempt to retry them (move back to candidates and reprocess).

## Phase 5: Summary report

After all candidates processed, print:

```
=== Discovery Run Complete ===
Total candidates processed: N
Papers that USE tools (reviewed): N
Papers that DON'T use tools (rejected): N
Needs full text (manual review): N
Errors: N
```

## Phase 6: Update last run date

If running in weekly or --since mode, update `last_discovery_run` in
`discovery_config.yaml` to today's date.
