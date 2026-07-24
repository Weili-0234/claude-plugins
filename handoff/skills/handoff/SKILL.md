---
name: handoff
description: Use when wrapping up or pausing a Claude Code session and the work needs to be handed off — the user asks to "do a handoff", "hand off", "write a handoff", save the current state/progress, transfer work to another person or a future session, or types /handoff so someone can pick it up cleanly later.
---

# Handoff

## Overview

Produce a single handoff document so another person — or a future session with no memory of this one — can pick up the work cleanly. Core principle: **write for a reader with zero context, and ground every line in what actually happened this session.** Never invent.

## When to use

- The user says "do a handoff", "hand off", "write a handoff", or types `/handoff`.
- Wrapping up, running low on context, or pausing a long task to resume later.
- Transferring work to a teammate or a fresh session.

## Procedure

1. **Timestamp.** Run `date +%Y-%m-%d-%H%M` to get the current date and time. Do not hand-type the date.
2. **Mine the session, then verify with tools.** Review the conversation for what happened — but don't write the document from memory alone. Handoff runs in the normal loop with full tool access, so confirm the facts that matter before committing them to the page: `git status` / `git diff --stat` for branch and uncommitted changes; `grep`/Read to pin exact `path:line`; and check that artifact/result/output paths, run IDs, and reported metrics actually exist and read as claimed. If you cannot verify something, mark it as unverified rather than stating it as fact.
3. **Write the file** into the current working directory as `handoff-<timestamp>.md` (e.g. `handoff-2026-06-07-1130.md`). Body in **English**. Use the eight sections below, in this exact order, with these exact headings.
4. **Report back** the file path and a one-line summary.

## Sections (exact order, all `##` headings)

Write every section in real detail — completeness over brevity. If a section genuinely has nothing, write `_None._` rather than dropping it. The `#` title line is just a title; the eight `##` sections below are required.

| Section | What goes in it |
|---------|-----------------|
| **Status** | The richest section — write it most thoroughly, several paragraphs. Orient a reader with zero context: the objective/goal and why it matters; where things stand now (phase, overall progress); what is working vs. broken/blocked; and environment state (branch, uncommitted changes, running services, key paths/endpoints, prerequisites). If a reader reads only this section, they should understand the situation. |
| **Done** | What was completed this session. Each item: what changed, where (`path:line`), and the resulting effect or how it was verified. |
| **Experiments & analyses** | Reproducibility record for two kinds of empirical work: **(A)** experiments/benchmarks you ran (e.g. sending traffic to a GPU inference system and measuring throughput/latency), and **(B)** analyses of data you fetched (e.g. downloading logs/traces and computing average KV cache hit rate, or reconstructing sessions / radix-tree context growth). Write so the next person can reproduce it from scratch and get the same numbers. Use `_None._` only if genuinely none was done. One sub-block per item — see the templates below. Bookkeep **everything**, not a headline metric or two. |
| **Todo** | Outstanding work. Each item carries enough context to act on: why it matters and what it touches. |
| **Decisions** | Key decisions made, the reasoning behind each, and alternatives that were considered but rejected — so the next person does not relitigate them. |
| **Pitfalls** | Traps, gotchas, counter-intuitive behavior, and anything that wasted time. |
| **Next** | The concrete first step to take on pickup — specific and immediately actionable. |
| **Files** | Key files touched or relevant, each with a one-line note on its role; `path:line` where useful. |

### Experiments & analyses — templates

Two flavors show up; use whichever fits (or both, one sub-block each). The guiding principle for both: a reader should be able to reproduce the work, locate every artifact, re-derive every number, and understand what it meant — without asking you anything. Record raw paths and commands **verbatim**; never paraphrase a command you actually ran.

**A. Experiment runs** (you generate the data — e.g. send traffic and measure throughput/latency). Capture all six fields:

- **Goal / hypothesis** — what this run was testing and the question it was meant to answer.
- **Setup** — the full configuration, enough to reconstruct the run exactly: system under test and its version/commit/image tag; hardware (cluster, node, GPU count/type); model and quantization; serving engine and flags; the workload (request rate, concurrency, input/output token lengths, dataset/prompt source, total requests, warmup); seeds; and any env vars or secrets needed (name them, don't paste values).
- **Reproduce** — the exact script(s) and command(s) to relaunch the run, with absolute paths and arguments. Include how to start the system under test, how to generate/send the traffic, and how to vary key knobs. If a launcher script exists, point to it (`path:line`); if you ran ad-hoc commands, record them verbatim.
- **Artifacts & results** — where **all** outputs live: raw result files (paths, S3/GCS buckets, `/shared` paths, run IDs), server and client logs, traces/profiles, dashboard links (Grafana, W&B), and any saved configs. Record **all** metrics, not a cherry-picked subset — throughput (req/s, tok/s in+out), latency distribution (p50/p90/p95/p99, TTFT, ITL/TPOT), GPU utilization and memory, batch sizes, error/timeout counts. A table of full results beats prose.
- **Analysis** — the exact script(s)/notebook(s)/commands used to turn raw artifacts into the reported numbers (`path:line` or verbatim command), plus how to re-run them. Note any manual steps so they aren't lost.
- **Findings & takeaways** — what the numbers show, the conclusion drawn, caveats and anomalies (warmup effects, outliers, suspected measurement error), and what to try next.

**B. Log/trace analyses** (you consume data you fetched — e.g. download logs/traces and compute average KV cache hit rate, reconstruct sessions / radix-tree context growth). Capture all five fields:

- **Data source / provenance** — exactly where the data came from and how you obtained it: origin (cluster pod + path, Loki/Grafana query, S3/GCS URI, web URL, run ID), the **verbatim fetch command** (`kubectl cp …`, `aws s3 cp …`, `curl …`), the time window covered, and the **local copy path** plus a fingerprint (line count / size / sha) so the next person can confirm they have the same input.
- **Scripts** — the analysis script(s) with absolute path (`path:line`), and what each computes (e.g. average KV cache hit rate, session reconstruction, radix-tree context-growth curve). Prefer a saved script over an inline one-liner; if it was a one-liner, record it verbatim.
- **Launch command** — the exact command used to run the script, **verbatim**, with every argument and the interpreter/env (e.g. `uv run python analyze_kv.py --input traces.jsonl --out results/kv_hit.txt`).
- **Results** — dump **all** results, not just the headline number, to a referable output file (`.txt`/`.csv`/`.jsonl`): per-session/per-request rows, full distributions, intermediate tables. Record that file's path so future turns can `grep`/read it instead of re-fetching and re-running. Quote only the headline numbers inline and point to the file for the rest.
- **Findings & takeaways** — what the analysis shows, the conclusion drawn, caveats and anomalies (truncated logs, clock skew, sampling bias), and what to try next.

## Output skeleton

```markdown
# Handoff — <short title> — <YYYY-MM-DD HH:MM>

## Status
<objective + why; where things stand; working vs. broken; environment — several paragraphs>

## Done
- <what changed, where (`path:line`), resulting effect / how verified>

## Experiments & analyses
### <experiment name / ID>   <!-- A. experiment run -->
- **Goal / hypothesis:** <what it tested>
- **Setup:** <system + version/commit/image; hardware (cluster/GPUs); model; engine + flags; workload (rate, concurrency, in/out lengths, dataset, #requests, warmup); seeds; env vars by name>
- **Reproduce:** <exact script(s)/command(s) with absolute paths and args — launch system, send traffic, vary knobs>
- **Artifacts & results:** <paths/buckets/run IDs for raw results, logs, traces, dashboards; full metrics table — throughput, p50/p90/p99, TTFT, ITL/TPOT, GPU util/mem, errors>
- **Analysis:** <exact analysis script(s)/notebook(s) (`path:line` or verbatim command) and how to re-run>
- **Findings & takeaways:** <what the numbers show; conclusion; caveats/anomalies; what to try next>

### <analysis name / ID>   <!-- B. log/trace analysis -->
- **Data source / provenance:** <origin (pod/path, Loki query, S3 URI, URL, run ID); verbatim fetch command; time window; local copy path + line count/size/sha>
- **Scripts:** <analysis script(s) (`path:line`) and what each computes>
- **Launch command:** <verbatim command with all args and interpreter/env>
- **Results:** <referable full-dump file path (.txt/.csv/.jsonl) holding ALL rows/distributions; headline numbers inline>
- **Findings & takeaways:** <what it shows; conclusion; caveats/anomalies; what to try next>

## Todo
- <outstanding item + the context needed to act on it>

## Decisions
- <decision> — <why; alternatives considered and rejected>

## Pitfalls
- <trap / gotcha / time-sink and how to avoid it>

## Next
1. <concrete, immediately actionable first step on pickup>

## Files
- `path:line` — <role / what to know about it>
```

## Common mistakes

- **Wrong filename.** It must be `handoff-YYYY-MM-DD-HHMM.md` from `date +%Y-%m-%d-%H%M`, written into the current working directory — not `HANDOFF.md` and not a hand-typed date.
- **Renaming or reordering sections.** Use the eight headings above, in order. Do not substitute "TL;DR", "Summary", "Root cause", etc.
- **Thin Status.** Status is the orientation section; a one-liner defeats its purpose. Make it the most detailed part of the document.
- **Cherry-picked or unreproducible experiments/analyses.** Recording one or two headline metrics, paraphrasing the command instead of the verbatim invocation, or omitting where the raw artifacts/logs/traces live. The Experiments & analyses section must let the next person reproduce the work and re-derive every number — capture all fields and all metrics, not the highlights.
- **Lossy log/trace analyses.** For data you fetched: failing to record the data source/provenance and the verbatim fetch command, or saving only the summary number instead of dumping the full results to a referable `.txt`/`.csv`/`.jsonl` file. Future turns must be able to query the complete output (per-session rows, distributions, intermediate tables) without re-fetching and re-running.
- **Writing from memory instead of verifying.** Stating branch state, `path:line`, artifact/result paths, or metrics from recollection when a quick `git status` / `grep` / Read / file check would confirm them. Memory drifts over a long session — verify the facts that matter, and flag anything you couldn't.
- **Inventing content.** If you did not see it this session, do not claim it. Use `_None._` for genuinely empty sections.
