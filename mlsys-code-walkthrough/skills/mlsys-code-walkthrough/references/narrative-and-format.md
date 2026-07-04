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

- Good: "上一节确立了 `out_cache_loc` 同时是第一个池的返回值和第二个池的索引；这一节看它在 prefill 时如何被分配。"
- Good: "回顾 spine 第 5 步 `run_batch` 把 `ScheduleBatch` 转成 `ModelWorkerBatch`——这一步具体改了哪些字段？"
- Bad: "有了这些基础，我们来看……" / "接下来讨论……" (carry no derivation).

## The driving question

Every article answers one explicit question — its spine. State it early, *after* enough
background that the reader can feel its weight ("How does a token's KV cache get allocated,
used, and freed across prefill and decode?"). Every later section visibly serves it.

## Heading hierarchy

- `#` — article title (once). Bilingual is fine: `# SGLang 后端代码解析`.
- `##` — one per component/stage/phase. Title bilingually: `## 中文描述 (English Description)`,
  e.g. `## Scheduler 接收请求以及处理批次 (Scheduler Receive Requests and Process Batches)`.
- `###` — one per function; **the heading text IS a GitHub permalink** to that function.
  Join two related functions with ` 和 `: `### [forward_extend](url) 和 [forward_decode](url)`.
- `#####` — lifecycle steps inside a phase (`##### Step 1. Function \`get_new_batch_prefill\``).
- Group engineering challenges that stem from one design decision under a single `##`, each
  as a `###` whose title encodes the constraint it answers ("避免动态内存分配").

## Code citation rhythm

Pin ONE commit for the whole article. Every link is
`https://github.com/<org>/<repo>/blob/<commit>/<path>#L<start>-L<end>`. Never link `main`.
The rhythm around a code block:

1. **Source + purpose sentence**: "对应源码在 [`model_runner_kv_cache_mixin.py`](permalink)：" — name where it is and what it does, in one sentence.
2. **The code block**, language-tagged. For long bodies, wrap in `<details><summary>…源码</summary>` so the main line stays readable — this is the repo's universal container for full function bodies.
3. **Numbered step-by-step analysis** below it, in execution order, tying each step to the data-structure effect.

A lighter alternative for incidental functions: skip the permalink and use an inline
parenthetical — "...写入 KV cache（函数 `save_kv_cache`）". Use sparingly; prefer permalinks for
anything on the lifecycle spine.

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
Open each part by recalling the previous part's result and stating this part's scope ("在
[Part 1](readme.md) 中我们介绍了初始化，本篇进入训练过程"), and cross-link specific anchors.

## Language

Chinese-first prose; technical terms stay in English (`ScheduleBatch`, prefill, radix tree,
KV cache, TP — never force a translation); no space between Chinese and English. Code and
code comments stay in their original language. Produce `readme-en.md` only on request, with
headings/lists/tables/code/blockquotes/image-positions strictly mirroring the Chinese, and
internal `.md` links switched to their English counterparts.

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
- [ ] Diagrams are mermaid (no ASCII); overview edges labeled with the data that flows?
- [ ] Drawn plots (if any): one semantic color axis + legend, render self-checked, and the
      `.excalidraw` source committed next to the export?
- [ ] One pinned commit; every `###` function heading is a permalink with line range?
- [ ] Transitions reference a specific prior result, not "有了这些基础"?
- [ ] Implementation claims verified against the pinned source?
- [ ] Personal-blog flourishes removed; lead is driving-question + roadmap?
