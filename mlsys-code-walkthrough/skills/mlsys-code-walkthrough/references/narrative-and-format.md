# Narrative frame, format, and self-check

The Awesome-ML-SYS-Tutorial walk-throughs read well because of a small set of structural
habits. This session uses the **technical-structural** voice: keep all the rigor below; drop
the personal-blog flourishes (see the last section).

## Concept → model → code (hard ordering)

Never drop the reader into engineering code before they have the tools to read it. The order
is always:

1. **Concept frame** — the analytical tools: what the subsystem is, the mechanism, the
   constraints. Build this with prose, classification tables, and the design rationale.
2. **Concrete scenario/model** — the specific request / model / training step the article
   traces, so the concepts have something to bite on.
3. **Code** — real source, cited and analyzed, showing the concepts in action.

Reversing this (code first, concept later) is the most common failure. Don't.

## Progressive derivation, not checklists

Each section must *derive from the previous one's conclusion*, not merely follow it. A
constraint comes from a mechanism; an engineering decision comes from a constraint. Don't
dump "five constraints" as a flat table and move on — thread them: introduce a constraint
where the mechanism forces it, then later "this is exactly the pointer-stability constraint
from §1." Section transitions must reference a specific prior result or open question:

- Good: "The previous section established that `out_cache_loc` is both the first pool's
  return value and the second pool's index; this section follows how it gets allocated
  during prefill."
- Good: "Recall spine step 5, where `run_batch` turns a `ScheduleBatch` into a
  `ModelWorkerBatch` — which fields does it actually rewrite?"
- Bad: "With these foundations in place, let's look at…" / "Next we discuss…" (carry no
  derivation).

## The driving question

Every article answers one explicit question — its spine. State it early, *after* enough
background that the reader can feel its weight ("How does a token's KV cache get allocated,
used, and freed across prefill and decode?"). Every later section visibly serves it.

## Heading hierarchy

- `#` — article title (once), in English: `# SGLang Backend Code Walk-through`.
- `##` — one per component/stage/phase, titled in English:
  `## Scheduler Receives Requests and Processes Batches`. (The Chinese mirror may title
  bilingually: `## 中文描述 (English Description)`.)
- `###` — one per function; **the heading text IS a GitHub permalink** to that function.
  Join two related functions with ` and `: `### [forward_extend](url) and [forward_decode](url)`.
- `#####` — lifecycle steps inside a phase (`##### Step 1. Function \`get_new_batch_prefill\``).
- Group engineering challenges that stem from one design decision under a single `##`, each
  as a `###` whose title encodes the constraint it answers ("Avoiding dynamic memory
  allocation").

## Code citation rhythm

Pin ONE commit for the whole article. Every link is
`https://github.com/<org>/<repo>/blob/<commit>/<path>#L<start>-L<end>`. Never link `main`.
The rhythm around a code block:

1. **Source + purpose sentence**: "The source is in [`model_runner_kv_cache_mixin.py`](permalink):" — name where it is and what it does, in one sentence.
2. **The code block**, language-tagged. For long bodies, wrap in `<details><summary>…source</summary>` so the main line stays readable — this is the repo's universal container for full function bodies.
3. **Numbered step-by-step analysis** below it, in execution order, tying each step to the data-structure effect.

A lighter alternative for incidental functions: skip the permalink and use an inline
parenthetical — "…writes the KV cache (function `save_kv_cache`)". Use sparingly; prefer
permalinks for anything on the lifecycle spine.

## Format conventions

- **Bold** the definition of a key concept and each core conclusion; bold the first
  appearance of an important term. Don't over-bold.
- **Blockquotes** (`>`) for an important caveat or a definition pulled out for emphasis — not
  for long body text.
- **`<details>`** for optional depth and full code: keeps the main thread skimmable. The
  `<summary>` must say what's inside.
- **Tables** for comparison/classification and for the sibling-function operation matrix
  (`lifecycle-tracing.md`). **Numbered lists** for ordered steps; **bullets** for parallel
  items, each leading with its point.
- **Cross-links**: relative paths within the repo (switch to the matching language version
  when translating); commit-pinned URLs for external code. Link to a specific `###` anchor in
  a sibling article when referencing a prior result.

## Series / multi-part

Large subsystems split into parts (`readme.md`, `readme-2.md`, …) or sections of one doc.
Open each part by recalling the previous part's result and stating this part's scope
("[Part 1](readme.md) covered initialization; this part enters the training loop"), and
cross-link specific anchors.

## Language

English-first prose. Code and code comments stay in their original language. **All figure
text is English-only**: mermaid node/edge labels, Excalidraw box/arrow/legend labels, and
any svg/png export. There is exactly one set of figure files per article.

### The Chinese mirror (`readme-CN.md`) — conditional subagent contract

Produce `readme-CN.md` ONLY when the user's request is in Chinese or mixes Chinese and
English. For English-only requests, do not create a Chinese version at all.

When triggered: after the English `readme.md` is finished and self-checked, fan out a
subagent to write `readme-CN.md` next to it; on every later revision of `readme.md`,
re-run the subagent to update the mirror. Give the subagent this contract:

- **Strict structural mirror**: same headings (the `##` titles may be bilingual
  `## 中文描述 (English Description)`), lists, tables, code blocks, blockquotes, and image
  positions as the English version, 1:1.
- **Translate prose only.** Technical terms stay in English (`ScheduleBatch`, prefill,
  radix tree, KV cache, TP — never force a translation); no space between Chinese and
  English. Code and code comments are NOT translated.
- **Figures are shared, never re-drawn**: embed the SAME image paths the English version
  uses (labels stay English). Do not create `_zh`/`_CN` figure variants.
- **Links**: internal `.md` cross-links switch to their Chinese counterparts when one
  exists; commit-pinned external URLs carry over unchanged.
- The vocabulary rule below binds the mirror too: no coined Chinese abstractions, and no
  Chinese coinages replacing the code's English terms.

**Vocabulary comes from the codebase, never from you.** Unless the codebase literally has a
keyword called xxxx (grep identifiers, docstrings, comments to check), you may not coin
xxxx as a new abstraction — in either language. Two failure modes observed in practice
(2026-07 user feedback):

- *Invented metaphor*: calling an admitted external execution a "lease/租约" when the code
  only ever says "holding its dispatch slot" + "reap deadline" — the reader greps the repo
  for the article's words and finds nothing.
- *Awkward Chinese coinage for an existing English term*: 槽位 for slot, 托管 for held
  results. Keep the code's English term verbatim inside Chinese prose (dispatch slot,
  held results, custody debt, inferred chain edge, born terminal, eviction seam...).

If the mechanism genuinely has no name in the code, don't name it — describe it in one
plain sentence composed of the code's own words (quote the docstring if one exists).

## KEEP vs DROP (technical-structural voice)

KEEP (this is the rigor that makes it a good walk-through):
- concept→model→code ordering; progressive derivation; the driving question
- data-flow diagrams; data-structure Shape/Access tables; the lifecycle mutation trace
- alternative-comparison tables; show design evolution (baseline → intermediate → final)
- the "why not X" pattern: explain what X solves, why this scenario doesn't need it, conclude
- explicitly distinguish what a unifying change *does* and *doesn't* couple
- concrete numerical examples; verify implementation claims against source

DROP (personal-blog flourishes — not wanted for internal engineering docs):
- first-person motivation anecdotes ("前几天和 X 在研究…时发现自己知之甚少")
- acknowledgements lists ("感谢各位大哥…"), and "本文基于 commit xxx 进行分析" boilerplate
  (the commit appears naturally in the links instead)
- self-deprecation, humor, 文人相赏, personal knowledge-source attributions

Replace the personal opening with a tight lead: the driving question + a ≤4-item numbered
roadmap of what the article covers. A one-line neutral framing of *why this subsystem
matters* is fine; a personal story is not.

## Final self-check

- [ ] Concept frame precedes code? Driving question stated and visibly served?
- [ ] 3–6 key data structures, each with Shape/Access + a concrete number + how it cross-links?
- [ ] End-to-end spine list present (`<component> <function> <data-structure transition>`)?
- [ ] Every lifecycle step tags a verb (Allocate/Write/Update/No change/Free) + a worked number?
- [ ] Sibling functions in a comparison table with the divergence bolded?
- [ ] Cross-component: ownership, boundary object, and side-effects (e.g. flush_cache) all covered?
- [ ] Figures are drawn Excalidraw plots rendered to svg/png (no ASCII; mermaid only if
      the user explicitly asked); data-flow edges/arrows labeled with the data that flows?
- [ ] Drawn plots: one semantic color axis + legend, render self-checked, the
      `.excalidraw` source committed next to the export, and ALL figure text in English
      (mermaid labels included, if mermaid was requested)?
- [ ] If the user asked in Chinese or mixed Chinese-English: `readme-CN.md` fanned out to /
      updated by a subagent, strictly mirroring the English structure and embedding the
      SAME English-labeled figure files? (Skipped entirely for English-only requests.)
- [ ] One pinned commit; every `###` function heading is a permalink with line range?
- [ ] Transitions reference a specific prior result, not "with these foundations in place"?
- [ ] Implementation claims verified against the pinned source?
- [ ] Every concept word in the article greps in the codebase? (No coined abstractions —
      lease/租约-class metaphors — and no Chinese coinages replacing the code's English terms?)
- [ ] Personal-blog flourishes removed; lead is driving-question + roadmap?
