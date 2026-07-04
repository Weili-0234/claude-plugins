# Data-flow diagrams in mermaid

Author diagrams mermaid-first: an LLM can emit mermaid directly, it renders on GitHub, and
it diffs cleanly. (The repo's *polished* docs mostly ship static images — but many of those
are just rendered mermaid whose source was never committed, e.g. `sglang-omni/mermaid-redraw/`.
If you replace a mermaid block with a rendered/styled image, keep the mermaid source as an
unrendered appendix — `## 附录：流程图 Mermaid 源码`, the convention in
`sglang/code-walk-through/multimodal_request_lifecycle.md`.) **Never use ASCII art**
(`┌┐└┘│├─`) — it breaks across devices. Comparisons go in tables, linear paths in numbered
lists, and only true graphs/sequences/state-machines become diagrams.

## Pick the diagram type by job

| job | mermaid type |
|---|---|
| component / data-flow overview (who passes what to whom) | `flowchart`/`graph` with subgraphs |
| cross-component call + data exchange over time, async, threads | `sequenceDiagram` |
| one object/structure moving through states | `stateDiagram-v2` |
| a structure's memory layout before/after an allocation | two small `flowchart`s, or a table |

A typical walk-through has one overview `flowchart` near the top, plus targeted diagrams per
section. Put the diagram *first* in its section and let the prose be step-by-step commentary
on it ("我们顺着图里的步骤走一遍").

## Convention 1 — staged data flow (`graph TD` + numbered subgraphs)

Group each pipeline stage into a `subgraph` labeled `<number>. <stage name> - <file.py>`, so
the diagram doubles as a table of contents that maps stages to source files. Nodes are
double-quoted strings; connect a stage's exit node to the next stage's entry node *outside*
both subgraphs. Adapted from the multimodal request lifecycle:

```mermaid
graph TD
    A["用户请求 POST /v1/chat/completions"] --> B1
    subgraph S1 ["1. Serving 层 - serving_chat.py"]
        B1["接收 FastAPI 请求"] --> B2["应用 chat template"] --> B3["构建 GenerateReqInput"]
    end
    B3 --> C1
    subgraph S2 ["2. Tokenizer 层 - tokenizer_manager.py"]
        C1["tokenize"] --> C2["构建 input_ids / mm_items"]
    end
    C2 --> D1
    subgraph S3 ["3. 调度层 - scheduler.py"]
        D1["创建 Req"] --> D2["Radix Cache 前缀匹配"] --> D3["加入 ScheduleBatch"]
    end
    D3 --> E["ForwardBatch → model.forward → logits → 采样"]
```

When data structures matter more than files, name the structure on the edge (see Convention
4) or make nodes the structures themselves.

## Convention 2 — nested phases for a training loop (`flowchart LR`)

For a step that cycles (rollout → make-experience → train → sync → repeat), use `flowchart LR`
with one subgraph per phase and an edge that closes the loop. Adapted from verl:

```mermaid
flowchart LR
    subgraph Init["Initialize"]
        direction TB
        A[TaskRunner] --> B[RayPPOTrainer] --> Workers
        subgraph Workers["Workers"]
            direction TB
            WA[ActorRolloutWorker] --> WD[FSDP Engine] --> WE[SGLang Engine]
        end
    end
    subgraph Loop["Train Loop"]
        direction TB
        E[DataLoader] --> R
        subgraph R["Rollout"]
            F1[Prepare Data] --> F2[SGLang Rollout] --> F3[Multi-turn]
        end
        R --> X
        subgraph X["Make Experience"]
            G1[Recompute LogProbs] --> G2[Reward] --> G3[Advantage]
        end
        X --> U
        subgraph U["Train"]
            H1[Load Weights] --> H2[Gradient] --> H3[Update] --> H4[Sync Weights]
        end
        U --> E
    end
    Init --> Loop
```

`direction TB` inside an `LR` graph stacks a subgraph's internals vertically while phases
flow left-to-right — this keeps wide pipelines readable.

## Convention 3 — async / cross-process exchange (`sequenceDiagram`)

When timing, threads, or request/response across a process boundary is the point, use
`sequenceDiagram` with `autonumber`, explicit `loop` blocks for background threads, and
`activate`/`deactivate` bars to show who holds the call. Label arrows with the call and the
data returned. Adapted from AReaL:

```mermaid
sequenceDiagram
    autonumber
    participant User as Main (Train Loop)
    participant Exec as WorkflowExecutor
    participant Engine as RemoteSGLangEngine
    participant SGLang as SGLang Server (HTTP)

    User->>Exec: prepare_batch(dataloader)
    loop Worker
        Exec->>Engine: agenerate(prompts)
        activate Engine
        Engine->>SGLang: HTTP POST /generate
        SGLang-->>Engine: Response (text)
        Engine-->>Exec: Trajectory (tensors)
        deactivate Engine
    end
    Exec->>User: wait() -> Batch of Trajectories
```

Use solid `->>` for calls, dashed `-->>` for returns. The returned-data label (`Trajectory
(tensors)`) is where you show what crosses the boundary.

## Convention 4 — object state machine (`stateDiagram-v2`)

For a structure that is fundamentally a state machine (a multi-turn rollout request, a
request's prefill→decode→finished progression), draw the states and label transitions with
the function/condition that fires them. Adapted from verl's tool-calling loop:

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> RUNNING : _handle_pending_state()
    RUNNING --> TOOL_CALLING : detect_tool_call
    TOOL_CALLING --> RUNNING : tool_call_executed
    RUNNING --> COMPLETED : stop_reason == STOP
    RUNNING --> [*] : finish_reason == LENGTH
    note right of RUNNING
        if exceeds max length: finish_reason = LENGTH
    end note
```

Transition labels are the *functions or conditions* that drive the change — this ties the
diagram back to the lifecycle-tracing prose.

## Edge labels = the data that moves

In a data-flow diagram, prefer edges that name the payload, so the picture itself answers
"what flows here": `Scheduler -->|ModelWorkerBatch| TpModelWorker`,
`FSDP -->|named_tensors| SGLang`, `Rollout -->|list[Sample]| Buffer`. An overview where every
edge is labeled with the structure crossing it is the strongest single artifact in the
article.

## When mermaid isn't enough: drawn plots

For a polished "hero" architecture diagram beyond mermaid's layout — nested containers with
semantic color tiers, ①-numbered data paths with a payload legend, ×N replica stacks,
CPU–GPU timelines — **author an Excalidraw plot yourself**: generate the `.excalidraw`
scene, render it via kroki, self-check the render, and commit source + export. Full method,
visual grammar, and element builders: `excalidraw-plots.md` (+ `templates/excalidraw_kit.py`).
The repo precedents are `sglang/code-walk-through/sglang_scheduler.svg` and
`rlhf/verl/multi-turn/imgs/agentLoop.png` (both Excalidraw). Default to mermaid; reach for
a drawn plot only for the one or two figures whose layout carries meaning mermaid can't
express. To rasterize *mermaid* locally if a static asset is wanted:
`npx -p @mermaid-js/mermaid-cli mmdc -i diagram.mmd -o diagram.svg`.

Embed any rendered figure centered, always with alt text:

```html
<div style="text-align: center; width: 100%; margin: 0 auto;">
    <img src="./images/architecture.svg" alt="<framework> 整体架构" style="width: 100%; height: auto;">
</div>
```

(Or `<div align="center"><img src="./x.png" alt="..." width="50%"></div>` for a smaller
figure.)

## Pitfalls

- **One mega-diagram.** Split: one overview + per-section zoom-ins beats a 40-node wall.
- **Unlabeled edges in a data-flow graph.** If the article is about data flow, the edges
  should say what flows.
- **Diagram that contradicts the prose.** Generate the diagram from the same lifecycle trace
  you wrote; re-check node/function names against the pinned source.
- **Mermaid syntax that won't render.** Keep node text in double quotes when it contains
  punctuation/parentheses/CJK; avoid raw `<`/`>`/`#` inside labels.
