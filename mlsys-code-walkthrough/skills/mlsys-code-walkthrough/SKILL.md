---
name: mlsys-code-walkthrough
description: >-
  Use when writing a code walk-through / 代码解析 tutorial for an ML-systems codebase —
  inference engines (SGLang, vLLM), RL / post-training frameworks (slime, verl, Megatron),
  or any repo under ThunderAgent-v2 — in the style of the Awesome-ML-SYS-Tutorial repo.
  The signature of this style: trace the KEY DATA STRUCTURES (e.g. Req, ScheduleBatch,
  ForwardBatch, the KV-cache pools, the radix tree, rollout / experience buffers, weight
  handles) through their LIFECYCLE, showing which FUNCTION allocates / writes / updates /
  frees which structure at each stage, visualized with mermaid DATA-FLOW diagrams and
  drawn Excalidraw ARCHITECTURE PLOTS (FlexKV-style: nested containers, semantic color
  tiers, ①-numbered data paths + legend, ×N replica stacks, CPU–GPU timelines). Covers:
  discovering the key data structures in a target repo, tracing the function→structure
  mutation chain, drawing data-flow / sequence / state diagrams in mermaid, authoring +
  rendering + self-checking .excalidraw architecture figures, the concept→model→code
  progressive-derivation narrative, bilingual (Chinese-first) section conventions, and
  commit-pinned GitHub code citations. Progressive disclosure: this file is the index;
  load the matching reference on demand.
---

# ML-Sys code walk-through tutorials (Awesome-ML-SYS-Tutorial style)

## Overview

A "code walk-through" in this style is **not** a tour of files top-to-bottom. It is the
story of a few **key data structures** moving through a **lifecycle**, where every section
answers: *which function touches this structure here, and how does it change?*

The mental model — everything in the skill serves this one sentence:

> **Pick a lifecycle (a request, a training step, a weight update). Find the 3–6 data
> structures that carry state across that lifecycle. Then walk the lifecycle stage by
> stage, and at each stage name the function and state precisely what it allocates /
> writes / updates / frees in those structures — drawn as a mermaid data-flow diagram and
> grounded in commit-pinned source.**

This is what makes the Awesome-ML-SYS-Tutorial walk-throughs feel rigorous: the reader can
always trace *why* the system is in a given state back to a specific function call on a
specific structure. The two canonical exemplars in that repo are
`sglang/code-walk-through/readme-CN.md` (a request through Server → Scheduler → Worker →
ModelRunner → Detokenizer) and `sglang/kvcache-code-walk-through/readme.md` (the KV-cache
pools through allocate → write → free). Study them; this skill distills their method.

## When to use

- Writing a new walk-through for a subsystem of SGLang, vLLM, slime, verl, Megatron, or
  another ML-systems repo (the repos under `~/code/ThunderAgent-v2/` are the usual targets).
- Documenting "how a request / training step / weight sync actually flows" through a
  codebase, where the value is in the data-structure transitions, not prose.
- Extending or revising an existing walk-through in the Awesome-ML-SYS-Tutorial repo.

If the task is a conceptual explainer with no source-tracing (e.g. "explain GRPO"), this
skill is overkill — only the narrative conventions in `references/narrative-and-format.md`
apply.

## The method (six steps)

1. **Frame the lifecycle + driving question.** Decide the spine: *one* request, *one*
   training step, *one* weight update. State the driving question the article answers
   ("how does a token's KV cache get allocated, used, and freed?"). Pin ONE commit hash for
   the whole article now (see `references/finding-the-code.md`).
2. **Discover the key data structures.** Locate the 3–6 structures that carry state across
   the lifecycle, and for each capture its *shape*, *what each dimension/field means*, and
   *how it cross-links to the others* (shared keys/indices). → `references/data-structures.md`.
3. **Trace function → mutation.** Walk the lifecycle in execution order. At each stage,
   name the function and tag its effect on each structure with a verb: **Allocate / Write /
   Update / No change / Free**. Anchor every step in a concrete worked example with real
   numbers. → `references/lifecycle-tracing.md`.
4. **Draw the diagrams.** Mermaid for flow/sequence/state (`references/diagrams.md`). For
   the hero architecture figure — nested containers, semantic color tiers, numbered data
   paths ①②③ with a payload legend, ×N replica stacks, CPU–GPU timelines — author an
   Excalidraw plot, render it, and self-check the render. → `references/excalidraw-plots.md`.
5. **Write it concept → model → code, with progressive derivation.** Build the concept
   frame first, then the concrete scenario, then the code. Each section must derive from
   the previous one's conclusion, not just follow it. → `references/narrative-and-format.md`.
6. **Cite, pin, self-check.** Every source reference is a GitHub permalink with the pinned
   commit hash + line range; the `###` heading for a function *is* its permalink. Run the
   checklist in `references/narrative-and-format.md`.

## Reference files (load the one you need)

| file | read it when |
|---|---|
| `references/data-structures.md` | identifying and presenting the key data structures: the `Shape / Access / Value` format, making shapes tangible with real numbers, and the cross-linking-via-shared-index technique that ties structures together. |
| `references/lifecycle-tracing.md` | the core method — tracing which function mutates which structure across the lifecycle: the per-step `Allocate/Write/Update/Free` format, the end-to-end overview list (the "spine"), the comparative table for sibling functions, and cross-component/distributed tracing (weight sync, rollout→train). |
| `references/diagrams.md` | drawing the data-flow diagrams in mermaid: which diagram type for which job, the subgraph-per-component convention, edge labels = the data that moves, state diagrams for a structure's lifecycle, and ready-to-adapt templates. |
| `references/excalidraw-plots.md` | drawing the hero architecture plot (FlexKV / `sglang_scheduler.svg` style) as an `.excalidraw` scene: the visual grammar (one semantic color axis, dashed container boundaries, payload-labeled or ①-numbered arrows + legend, ×N replica stacks, timeline plots), the `templates/excalidraw_kit.py` builders, the kroki render + headless-Chrome self-check loop, and committing source + export. |
| `references/narrative-and-format.md` | the writing frame: concept→model→code ordering, progressive derivation (no checklists), bilingual section titles, heading hierarchy, code-citation rhythm, what to KEEP vs DROP from the personal-blog voice, and the final self-check. |
| `references/finding-the-code.md` | analyzing a target repo before writing: where the key data structures live in SGLang / vLLM-v1 / slime / verl, grep recipes to find allocations and mutations, and how to pin a commit + build permalinks. |
| `templates/walkthrough-skeleton.md` | the skeleton to copy when starting a new article. |

## Cardinal rules (always)

- **Data structures are the protagonists.** If a section doesn't advance the story of a key
  structure's state, cut it or move it to a `<details>` block.
- **Every mutation gets a verb + a number.** Not "the scheduler processes the batch" but
  "`prepare_for_extend` *allocates* 2 slots in `token_to_kv_pool` for tokens B, C".
- **Pin ONE commit for the whole article.** All GitHub links use that commit hash +
  `#L<start>-L<end>`. Never link `main`/`master` line numbers — they rot. The `###` heading
  of a function is itself the permalink.
- **No ASCII-art diagrams.** Data flow → mermaid. Comparison / classification → markdown
  table. Linear path → numbered list. Hero architecture / replica topology / timeline →
  a drawn Excalidraw plot with its `.excalidraw` source committed and the render
  self-checked. (See `references/diagrams.md`, `references/excalidraw-plots.md`.)
- **Read the source before asserting.** Field names, shapes, and who-mutates-what must be
  verified against the pinned source, not guessed from memory or a tech report.
- **Concept before code, always.** Build the analytical frame first; never drop the reader
  into engineering code before they have the tools to read it.

## Output conventions (this session's defaults)

- **Language: Chinese-first.** Write the `readme.md` (or `readme-CN.md`) in Chinese; keep
  technical terms in English (ScheduleBatch, KV cache, prefill, radix tree — never force a
  translation), no space between Chinese and English. Produce the English version
  (`readme-en.md`) only on request, with format strictly mirrored.
- **Voice: technical-structural.** Keep the rigor — concept→code, data-flow diagrams,
  data-structure tables, lifecycle tracing, progressive derivation, alternative-comparison
  tables, the "why not X" pattern, distinguishing what-changes vs what-doesn't. DROP the
  personal-blog flourishes (first-person motivation stories, "感谢各位大哥" acknowledgements,
  self-deprecation, 文人相赏). Open with the driving question and roadmap, not a personal
  anecdote. (Details in `references/narrative-and-format.md`.)
- **Placement.** New articles live in the target repo's docs area or alongside the code
  under analysis, mirroring Awesome-ML-SYS-Tutorial's layout: `<topic>/code-walk-through/readme.md`
  plus an images/ dir for rendered diagrams — always containing the `.excalidraw` source
  next to each exported figure (the tutorial repo lost every diagram source; don't repeat that).
