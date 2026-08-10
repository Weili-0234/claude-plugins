# Lifecycle tracing — which function mutates which structure

This is the core of the method. Once you have the key data structures
(`data-structures.md`), walk the lifecycle in **execution order** and, at every stage, name
the function and state precisely what it does to each structure.

## The mutation verbs

Tag every effect with one verb. This vocabulary is what makes the tracing legible:

| verb | meaning |
|---|---|
| **Allocate** | reserve new slots/indices/memory (often returns indices used downstream) |
| **Write** | fill allocated slots with real data (KV tensors, token ids, logits) |
| **Update** | mutate existing fields/state (status, refcount, prefix, append a turn) |
| **No change** | explicitly note when a stage leaves a structure untouched (this is informative) |
| **Free / Release** | return slots/memory; decrement refcount; drop the object |

"No change" earns its place — readers wonder, so answer. The decode step's
`prepare_for_decode` note is a model: "`req_to_token_pool` — No change; `token_to_kv_pool` —
Allocate (batch_size × 1) slots because we generate one token per sequence."

## The per-step format

Each lifecycle stage is a heading that names the function, followed by bullets — one per
structure it touches — each with a verb and a concrete number from the running example:

```markdown
##### Step 1. Function `get_new_batch_prefill`
- Update the prefix from the radix tree (`match_prefix` hits `A`; the node splits into `A` and `FG`)
- Call `prepare_for_extend`:
  - `req_to_token_pool`: **Allocate** `req_pool_indices`, write the prefix
  - `token_to_kv_pool`: **Allocate** Σ(#input_ids − #prefix) `out_cache_loc` entries
    - In the example, request `ABC`, batch size = 1: input = 3 (A,B,C), prefix = 1 (A), so 2 slots are allocated for tokens B and C
```

Use `#####` for steps under a `####` phase (Prefill / Decode), and make the function name a
GitHub permalink (see `narrative-and-format.md`). Walk top-to-bottom in the order the code
runs. Anchor every allocation count in the *same* worked example.

## The end-to-end overview list (the spine)

Before the per-stage deep dives, give ONE numbered list that traces the whole lifecycle —
naming each component, the function called, and the data-structure transformation at each
hop. This is the article's spine; everything after it is zoom-in. The request walk-through's
spine (abridged, reproduce this shape):

> 5. The Scheduler processes requests in `event_loop_normal`:
>    - receives via `recv_requests`, processes via `process_input_requests`, and `handle_generate_request` adds them to the `waiting_queue`
>    - builds a `ScheduleBatch` from the `waiting_queue` via `get_next_batch_to_run`
>    - `run_batch` turns the `ScheduleBatch` into a `ModelWorkerBatch`
>    - calls TpModelWorker's `forward_batch_generation`, awaiting `logits_output` and `next_token_ids`
>    - TpModelWorker initializes a `ForwardBatch` and forwards it to the ModelRunner…
>    - `process_batch_result` handles the results; `cache_finished_req` caches finished requests…

Notice every line is `<component> <function> <data-structure transition>`. That triplet is
the unit. The reader can navigate the rest of the article from this list alone.

## The comparative table for sibling functions

When two functions are near-twins that differ in a few steps (allocate-path vs free-path,
prefill vs decode, finished vs unfinished), lay them side by side: **rows = the ordered
operations, columns = the variants, bold the divergence.** From the KV-cache article:

```markdown
| Step | `cache_unfinished_req` | `cache_finished_req` |
|------|--------------------------|--------------------------|
| 1. Take `kv_indices` from `req_to_token_pool` | - | - |
| 2. Update Radix Cache (`insert()`) | - | - |
| 3. Free KV Cache (`token_to_kv_pool.free()`) | - | frees the duplicated KV storage |
| 4. Handle `req_to_token_pool` | **write + update** | **free** (request finished) |
| 5. Handle `req.last_node` | **increment** refcount | **decrement** refcount (request finished) |
```

This single table conveys more than two paragraphs of prose, and the bolded cells point the
eye straight at what actually differs.

## Cross-component / distributed tracing

When the lifecycle is a training step or a weight sync spanning processes, the same method
applies, with three additions.

### 1. The call-chain section, early

Before deep dives, give the layered call chain so the reader sees who drives whom. slime's
form (reproduce this shape — layer → functions → effect):

> 1. Script layer (`scripts/`): start Ray → submit the job → pick `train.py`/`train_async.py`
> 2. Entry layer (`train*.py`): `create_placement_groups` allocates GPUs; `create_actor_group` builds the training actor group; `create_rollout_manager` builds the inference/data-generation manager
> 3. Execution layer (`ray/`+`backends/`): `actor_group.async_train(...)` → Megatron gradient computation; `rollout_manager.async_generate(...)` → SGLang batch inference; `actor_group.async_update_weights()` → pushes trained weights to the inference engine
> 4. Data flow (`buffer.py`): `Buffer` samples/batches/invokes generation → returns training samples

### 2. The data-object growth chain (pop / union)

For a step built around one exchange object, narrate it as a chain where each function
*adds a field*. verl's `DataProto` chain is the exemplar — show the `A → B → … → N` chain,
then the code at each link:

```python
gen_batch = batch.pop(batch_keys=["input_ids", "attention_mask", "position_ids"])  # extract rollout inputs
gen_batch_output = self.actor_rollout_wg.generate_sequences(gen_batch)             # rollout
batch = batch.union(gen_batch_output)                                              # merge responses back
batch.batch["token_level_rewards"] = self.reward_fn(batch)                         # reward → new field
batch = compute_advantage(batch, adv_estimator=...)                               # advantages → new field
old_log_prob = self.actor_rollout_wg.compute_log_prob(batch); batch = batch.union(old_log_prob)
critic_output = self.critic_wg.update_critic(batch)                                # consume
actor_output  = self.actor_rollout_wg.update_actor(batch)                          # consume
```

The story is literally "which function populates which key of `batch`." Tag each:
`generate_sequences` **writes** `responses`; `reward_fn` **writes** `token_level_rewards`;
`compute_advantage` **writes** `advantages`; `update_actor` **consumes** the lot.

### 3. Weight transfer — describe it at three levels

Cross-engine weight sync is a recurring, subtle flow. Always cover all three levels, in
order — skipping the third (side effects) is the most common gap:

1. **Architectural** — who gathers, who sends, who receives. ("FSDP engine gathers sharded
   weights → pushes to SGLang's `update_weights_from_tensor` → distributed across TP ranks.")
2. **The data structure crossing the boundary** — its exact type and how it's reshaped for
   the receiver's parallel layout. (`named_tensors: List[Tuple[str, torch.Tensor]]`;
   `WeightUpdateMeta` choosing NCCL-broadcast vs disk; FSDP `[256,1024]` shard → SGLang TP
   layout.)
3. **The side effects that MUST follow** — and *why*. The KV cache must be flushed because
   parameters changed and old KV is now invalid; the radix tree still indexes stale entries:
   > After the KV cache is released, the tensors remain but the physical memory backing
   > their virtual addresses is freed; meanwhile the radix tree still indexes the whole KV
   > cache. After resume, the old KV in physical memory is gone AND the model parameters
   > have been updated — for both reasons, the radix tree index must be refreshed through
   > the flush-cache interface.

   Other side effects to watch for: version-number bump, the lock that prevents concurrent
   rollout and weight broadcast, resume/pause of the inference engine.

## Pitfalls

- **Vague verbs.** "Processes the batch" hides the mutation. Say allocate/write/update/free.
- **No running example.** Counts ("2 slots", "1 slot") must trace one concrete request.
- **Out-of-order narration.** Follow execution order; if you must reference a later stage,
  link forward, don't reorder.
- **Forgetting "No change" and the side effects.** Both are where readers form wrong mental
  models. State them.
