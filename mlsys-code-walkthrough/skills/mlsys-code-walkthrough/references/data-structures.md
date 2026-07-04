# Key data structures — finding and presenting them

The data structures are the protagonists of the walk-through. Get this part right and the
rest writes itself; get it wrong and the article becomes a directionless file tour.

## Finding the 3–6 that matter

A key data structure is one that **carries state across the lifecycle** — it is created at
one stage, mutated at others, and read or freed at the end. You are looking for the nouns
that the verbs in the lifecycle act on. Heuristics:

- It appears in the signature or body of multiple lifecycle stages (created here, consumed
  there). Grep for a class name across the subsystem; if it shows up in 3+ files along the
  flow, it's a protagonist.
- It is explicitly described as global/persistent state ("KV Cache is the most important
  global state in the server"), or it is the object passed between components/processes
  (`DataProto`, `Sample`, `named_tensors`).
- It owns memory or indices that get allocated and freed (the pools, block tables, buffers).

Cap it at ~6. If you have more, some are implementation detail — demote them into the prose
of whichever stage touches them, or into a `<details>` block. The canonical KV-cache
walk-through tracks exactly three (`req_to_token_pool`, `token_to_kv_pool`, `tree_cache`);
the request walk-through tracks a handful of batch types (`ScheduleBatch`, `ModelWorkerBatch`,
`ForwardBatch`) plus the I/O structs (`GenerateReqInput`, `BatchTokenIDOut`, `BatchStrOut`).

## The presentation format

Introduce each structure with a heading, a one-line purpose, then a bullet block giving its
**Shape/Layout** and **Access** (what each dimension/field means, and what the value is).
This is the exact format from the KV-cache walk-through — reproduce it:

```markdown
#### `req_to_token_pool`
将 Request 映射到其 token 的 KV cache 索引。
- **形状（Shape）：** 最大并发 Request 数（由 `max-running-requests` 设置） × 每个 Request 的最大 token 数（由 `model_config.context_len` 设置）
- **访问（Access）：**
  - Dim0: `req_pool_indices`，定位具体的 Request
  - Dim1: token 在该 Request 中的位置（0, 1, 2, ...），定位具体的 token
  - 返回值：该 token 的 `out_cache_loc`，指向它在 KV cache 中的索引
```

Use the right container for the structure:

- **Bullet block with Shape/Access/Value** — for memory pools, tensors, tables (anything
  with dimensions). This is the default for inference-engine state.
- **Dataclass code block** — for plain record types crossing a boundary. Paste the real
  definition, then narrate the fields by role. From slime's `Sample`:
  ```python
  class Sample:
      prompt: Union[str, list[dict[str, str]]] = ""
      tokens: list[int] = field(default_factory=list)
      response: str = ""
      response_length: int = 0
      reward: Optional[Union[float, dict[str, Any]]] = None
      loss_mask: Optional[list[int]] = None
      class Status(Enum): PENDING="pending"; COMPLETED="completed"; TRUNCATED="truncated"; ABORTED="aborted"
      status: Status = Status.PENDING
  ```
  Then: who creates it, who mutates which field, who consumes it (see `lifecycle-tracing.md`).
- **Bullet list of sub-objects** — for a composite class, list its members by role, as the
  request walk-through does for the model class:
  > `Qwen2ForCausalLM` 的结构如下：
  > * `model`：用于前向传递的权重。
  > * `embed_tokens`：将 `input_ids` 转换为 embeddings。
  > * `lm_head`：将 hidden states 映射回 vocabulary space。

## Make the shape tangible with real numbers

Abstract shapes are forgettable; a worked number is not. Every structure with dimensions
gets a concrete instantiation. This is a hard habit from the repo:

> "假设这个参数的 size 是 `[1024, 1024]`，FSDP 的 TP size 是 4，而 SGLang 的 TP size 是 2。
> 因此在更新参数开始前，每个 rank 上在 FSDP engine 内有 `[256, 1024]` 大小的 tensor……"

For the pools: "max-running-requests = 4096, context_len = 8192 → `req_to_token_pool` is a
`[4096, 8192]` int table." Carry the *same* running example (a request for tokens "A B C")
through every structure and every lifecycle step so the reader builds one mental picture.

## The cross-linking technique (the signature move)

The thing that makes these articles click is showing how the structures **reference each
other through a shared key or index**. State it explicitly:

> 一个 token 在 `tree_cache`、`req_to_token_pool` 和 `token_to_kv_pool` 之间的数据，可以通过它的
> KV cache 索引（`out_cache_loc`）相互映射。

Concretely: `out_cache_loc` is the *value* returned by `req_to_token_pool` AND the *Dim1
index* into `token_to_kv_pool`. So a `(req_idx, position)` lookup in the first pool yields
an index that addresses the second pool. Always name the shared key that stitches your
structures together — it is the backbone of the data-flow diagram you'll draw later.

## Cross-component / distributed: add ownership and the boundary object

When the lifecycle spans processes or GPUs (training engine ↔ inference engine, actor ↔
rollout), two extra facts are mandatory for each structure:

- **Ownership** — which process/rank/actor holds the live object. ("`Sample` objects are
  owned by `RolloutController`, a Ray actor on the rollout side." "Only TP rank 0 holds live
  `AsyncRolloutRequest` objects; other ranks receive the final result via `broadcast_pyobj`.")
- **What actually crosses the boundary** — the serialized/handle form. ("`Box(ray.put(data))`
  puts the train dict into the Ray object store and returns a handle; the training actor
  calls `ray.get()` on it." "`named_tensors: List[Tuple[str, torch.Tensor]]` is what crosses
  the FSDP→SGLang boundary.")

The universal-exchange-object pattern is worth calling out when present, e.g. verl's
`DataProto` (a `TensorDict` `batch` + `non_tensor_batch` + `meta_info`) that every
worker-group RPC takes and returns — it is the single structure whose field-by-field growth
*is* the training-step story.

## Pitfalls

- **Don't paste a 200-line dataclass.** Show the 6–10 fields that participate in the
  lifecycle; collapse the rest or omit. Verify field names against the pinned source.
- **Don't introduce a structure you never mutate.** If it only gets read, it's context, not
  a protagonist — mention it inline.
- **Don't skip the shape.** "It holds the KV cache" is uselessly vague; give dimensions and
  what indexes them.
