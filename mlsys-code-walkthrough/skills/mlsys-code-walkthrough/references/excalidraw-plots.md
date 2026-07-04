# Drawn architecture plots (Excalidraw): author, render, self-check

Mermaid stays the default (`diagrams.md`). But the repo's best walk-throughs anchor on a
few **drawn plots** that mermaid cannot express — the hero architecture figure in
`sglang/code-walk-through/sglang_scheduler.svg` (an Excalidraw export), the Excalidraw
diagrams in `rlhf/verl/multi-turn/imgs/agentLoop.png` and `rlhf/areal/areal_overview.jpg`,
and the FlexKV-style figures this reference codifies. You CAN draw these yourself: author
an `.excalidraw` JSON scene, render it, look at the render, fix it, commit source + image.

The repo's own history says this matters twice over: (a) authors repeatedly wrote mermaid
first and later replaced it with a styled static figure (see the `mermaid-redraw/` commits
in `sglang/sglang-omni`), so the drawn plot is where good articles end up; (b) the repo
contains **zero** editable diagram sources — every existing PNG is terminal. Committing the
`.excalidraw` next to the exported image fixes that.

## When to draw a plot instead of (or on top of) mermaid

| signal | use |
|---|---|
| flow / sequence / state, structure is the content | mermaid (default) |
| hero architecture: nested containers ≥2 levels + semantic colors | drawn plot |
| numbered data paths ① ② ③ with a payload legend (FlexKV pattern) | drawn plot |
| replica / parallelism topology (× tp_size, × dp, N workers) | drawn plot (stack idiom) |
| CPU–GPU timeline, box width ∝ duration, sync points | drawn plot (timeline idiom) |
| memory / slot-grid layout (token→slot mapping) | drawn plot or markdown table |

Budget: **one, maybe two drawn plots per article** (the hero overview + at most one
zoom-in); everything else stays mermaid so it renders inline and diffs cleanly.

## The visual grammar (style contract)

Synthesized from the repo's Excalidraw exemplars + FlexKV's architecture figure. Follow it
so figures across articles look like one family.

1. **Color encodes exactly ONE semantic axis per figure.** Two sanctioned palettes
   (`PALETTE` in `templates/excalidraw_kit.py`, standard Excalidraw swatches):
   - *Role axis* (repo house style — `agentLoop.png` prints this as its legend):
     green=procedure/function · blue=engine/component · yellow=data object/buffer ·
     pink=network/resource endpoint · purple=queue/state · gray=replica/misc.
   - *Tier axis* (FlexKV style): pink=CPU · blue=GPU/SSD · yellow=remote/scalable ·
     green=queues · gray=scheduler.
   Same color = same meaning **everywhere in the figure**. >3 colors → print a legend
   (colored `label()` swatch lines, or a small boxed key top-right like `agentLoop.png`).
2. **Containers.** Outer **dashed** rectangle = component/process boundary, title as
   free text at its top-left (`label()`, not centered). Inner **solid** color-filled boxes
   = functions/objects/structures, name centered via `bind_text()`. Nesting ≥2 levels is
   normal (`areal_overview.jpg` nests 4). Dashed also means "not yet materialized /
   hypothetical" for single boxes — don't mix the two dashed meanings in one figure.
3. **Arrows.** Solid = synchronous call / main data path. Dashed = async, feedback,
   cross-boundary, control-plane. Every arrow on a data path carries its payload: either
   an inline bound label (`bind_text(arrow, ...)` → `-- ModelWorkerBatch -->`) or, when
   labels would clutter, a circled number (`num_badge()`) resolved in a legend:
   `① put/get: tokenlists, freeBlocksRequest`. The prose then either walks the numbers in
   order ("下图中 ① 时…，在 ② 时…" — `zero-overhead-batch-scheduler.md:133`) or, for a
   lifecycle spine, uses numbered `#####` step headers that map 1:1 onto the diagram's
   stages with backreferences ("在上图的例子中，Request `ABC`…" — the
   kvcache-code-walk-through pattern). When prose must decode a color/line style, the repo
   convention is an inline bolded phrase ("上图中**红色虚线**代表…"), never a standalone
   "Legend:" paragraph — the printed legend belongs inside the figure.
4. **Replicas.** N instances of a component = the `stack()` idiom: 2 offset dashed ghost
   boxes behind one solid box, annotated `× tp_size` / `× config.num_workers`
   (`agentLoop.png` uses exactly this with a brace).
5. **Timeline plots** (scheduler-overlap style, cf. `sglang/scheduler-evolution/img/`):
   one row per executor (CPU / GPU / CPU-S / CPU-L), boxes left→right on an implicit time
   axis, box width ∝ duration, thin arrows CPU-op → GPU-kernel it launches, red dashed
   vertical line = sync point, dashed empty box = step skipped in the optimized variant.
6. **Type.** fontFamily 1 (hand-drawn; CJK falls back to the embedded Xiaolai font — 中文
   直接可用) for everything except code identifiers where `family=3` (mono) is fine.
   Sizes: 18 container titles, 16 box labels, 14 arrow labels/badges, 15 legend.

## Authoring workflow

Work in a scratch dir; the deliverables that get committed are
`images/<fig>.excalidraw` + `images/<fig>.svg` (or `.png`).

1. **Plan on paper first**: list boxes with (x, y, w, h) on a rough grid — 10-unit grid,
   boxes ≥140×50, ≥30 gap between siblings, ≥28 headroom inside a container for its title.
   Total width ≤1200 units. Layout is the hard part; JSON is mechanical.
2. **Generate** with `templates/excalidraw_kit.py` (copy it next to your script):
   `rect / bind_text / label / arrow / num_badge / stack / save`. All coordinates must be
   Python numbers — see Pitfalls.
3. **Render** (kroki, needs network; content goes to kroki.io — fine for public-repo figures):

   ```bash
   curl -s -X POST -H "Content-Type: text/plain" --data-binary @fig.excalidraw \
        https://kroki.io/excalidraw/svg -o fig.svg
   ```

   The SVG is self-contained (fonts embedded as base64 woff2) — safe to commit and embed.
4. **Self-check loop** (mandatory — this is what makes the plot good): rasterize with
   headless Chrome and *look at it* with the Read tool; fix overlaps/clipping/spacing in
   the generator; re-render. Two or three passes is normal.

   ```bash
   read W H < <(python3 -c "import re;vb=re.search(r'viewBox=\"0 0 ([0-9.]+) ([0-9.]+)\"',open('fig.svg').read());print(int(float(vb.group(1)))+20,int(float(vb.group(2)))+20)")
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
       --screenshot=fig.png --window-size=$W,$H --default-background-color=FFFFFFFF "file://$PWD/fig.svg"
   ```

   Add `--force-device-scale-factor=2` (and keep `--window-size=$W,$H`) for a crisp 2× PNG
   if the PNG itself will be committed. Do NOT preview with `qlmanage` — it picks its own
   scale and crops.

   Check in the render: nothing clipped at the edges; no text overflowing its box; arrows
   attach to the boxes they mean; badges legible; legend colors match the boxes.
5. **Hand-polish (optional).** The `.excalidraw` file opens directly at excalidraw.com
   (menu → Open). Bindings from the kit survive, so dragging a box keeps its arrows
   attached. If you re-export from excalidraw.com, use SVG/PNG **with "embed scene"** so
   the export itself stays re-importable — then commit that export.
6. **Embed** with the repo's centered-div convention (see `diagrams.md`), alt text
   required — real alt text, not `alt text` placeholders. For figure-heavy articles the
   numbered-caption variant is the tts-optimization convention:
   `<div align="center"><img src="images/x.svg" alt="..." width="70%"><p><em>Figure 1. …</em></p></div>`.
   Keep the `.excalidraw` in the same `images/` dir as the rendered file. A translated
   (`readme-en.md`) version reuses the SAME image files and paths — never re-draw per
   language; only captions/prose change.

## Raw element schema (when not using the kit)

A `.excalidraw` file is `{"type":"excalidraw","version":2,"elements":[...],
"appState":{"viewBackgroundColor":"#ffffff"},"files":{}}`. Excalidraw fills in most
element fields on load; what you must get right:

- Common: `type`, unique `id`, numeric `x/y/width/height`, `seed` (any int),
  `strokeColor`, `backgroundColor`, `fillStyle` (`solid`|`hachure`), `strokeWidth`,
  `strokeStyle` (`solid`|`dashed`), `roughness` (1 = hand-drawn), `opacity` (100),
  `groupIds` ([]). Rectangles: `roundness: {"type":3}` or `null` for sharp corners.
- Text: `text`, `fontSize`, `fontFamily` (1 hand / 2 sans / 3 mono), `textAlign`,
  `verticalAlign`. Centered-in-box text: give the text `containerId: <box id>` AND push
  `{"id": <text id>, "type": "text"}` into the box's `boundElements` — both directions,
  or it renders as free text at its own x/y.
- Arrow: `points: [[0,0],[dx,dy],...]` relative to the arrow's `x/y`;
  `startArrowhead: null`, `endArrowhead: "arrow"`. Optional but recommended
  `startBinding`/`endBinding: {"elementId": <box id>, "focus": 0, "gap": 5}` (and add the
  arrow to each box's `boundElements`) so later manual edits keep endpoints attached.
  An inline payload label is a text element with `containerId: <arrow id>` + the matching
  `boundElements` entry on the arrow.
- Z-order = array order (later = on top): outer containers first, then inner boxes,
  arrows, badges, legend.

## Pitfalls (each one observed while building this pipeline)

- **A single non-numeric coordinate silently destroys the whole figure.** One string
  `"x"` NaN-poisons the scene bounding box → `viewBox="0 0 NaN NaN"` and every element
  renders at the origin. Coordinates, sizes, and `points` must all be numbers.
- **Trailing text clipped at the right/bottom edge.** kroki pads the content box by only
  ~10 units and trusts each text element's *declared* width, which you estimated. The
  kit's `save()` appends an invisible spacer for margin; still keep floating labels well
  inside the boxes' extent, and treat CJK glyphs as ~1.1× fontSize wide each.
- **Badges on short arrows.** A `num_badge()` centered on a <50-unit arrow hides the
  arrow; place the badge beside the arrow's midpoint instead.
- **Text wider than its box.** Bound text that doesn't fit gets wrapped/grown by
  excalidraw and layout shifts. Size boxes from label length (~0.75 × fontSize per latin
  char), or shorten the label.
- **Two semantic axes in one figure** (e.g. green=function AND green=queue) — the color
  story collapses; pick one axis per figure and legend it.
- **Editing the exported SVG by hand.** It's generated output; change the `.excalidraw`
  (or the generator script) and re-render. Commit both, always — this repo's 204 existing
  PNGs have no recoverable sources.
- **Redrawing a paper figure without credit.** If the plot adapts a figure from a paper or
  blog, link the source in prose right at the figure ("来源：[…](url)" — the
  `sglang-omni/README.md:622` convention); a watermark baked into pixels is not a citation.
