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
- 从 radix tree 更新 prefix（`match_prefix` 命中 `A`，节点分裂为 `A` 和 `FG`）
- 调用 `prepare_for_extend`：
  - `req_to_token_pool`：**Allocate** `req_pool_indices`，写入 prefix
  - `token_to_kv_pool`：**Allocate** Σ(input_id 数 − prefix 数) 个 `out_cache_loc`
    - 例子里请求 `ABC`，batch size = 1：input = 3 (A,B,C)，prefix = 1 (A)，故为 token B、C 分配 2 个 slot
```

Use `#####` for steps under a `####` phase (Prefill / Decode), and make the function name a
GitHub permalink (see `narrative-and-format.md`). Walk top-to-bottom in the order the code
runs. Anchor every allocation count in the *same* worked example.

## The end-to-end overview list (the spine)

Before the per-stage deep dives, give ONE numbered list that traces the whole lifecycle —
naming each component, the function called, and the data-structure transformation at each
hop. This is the article's spine; everything after it is zoom-in. The request walk-through's
spine (abridged, reproduce this shape):

> 5. Scheduler 在 `event_loop_normal` 中处理请求：
>    - 通过 `recv_requests` 接收，`process_input_requests` 处理，`handle_generate_request` 加入 `waiting_queue`
>    - 从 `waiting_queue` 用 `get_next_batch_to_run` 创建 `ScheduleBatch`
>    - `run_batch` 把 `ScheduleBatch` 转成 `ModelWorkerBatch`
>    - 调 TpModelWorker 的 `forward_batch_generation`，等待 `logits_output` 与 `next_token_ids`
>    - TpModelWorker 初始化 `ForwardBatch` 转发给 ModelRunner……
>    - `process_batch_result` 处理结果，`cache_finished_req` 缓存完成的请求……

Notice every line is `<component> <function> <data-structure transition>`. That triplet is
the unit. The reader can navigate the rest of the article from this list alone.

## The comparative table for sibling functions

When two functions are near-twins that differ in a few steps (allocate-path vs free-path,
prefill vs decode, finished vs unfinished), lay them side by side: **rows = the ordered
operations, columns = the variants, bold the divergence.** From the KV-cache article:

```markdown
| 步骤 | `cache_unfinished_req` | `cache_finished_req` |
|------|--------------------------|--------------------------|
| 1. 从 `req_to_token_pool` 取 `kv_indices` | - | - |
| 2. 更新 Radix Cache (`insert()`) | - | - |
| 3. 释放 KV Cache (`token_to_kv_pool.free()`) | - | 释放重复的 KV 存储 |
| 4. 处理 `req_to_token_pool` | **写入并更新** | **释放**（请求已完成） |
| 5. 处理 `req.last_node` | **增加**引用计数 | **减少**引用计数（请求已完成） |
```

This single table conveys more than two paragraphs of prose, and the bolded cells point the
eye straight at what actually differs.

## Cross-component / distributed tracing

When the lifecycle is a training step or a weight sync spanning processes, the same method
applies, with three additions.

### 1. The call-chain ("串联关系") section, early

Before deep dives, give the layered call chain so the reader sees who drives whom. slime's
form (reproduce this shape — layer → functions → effect):

> 1. 脚本层（`scripts/`）：启动 Ray → 提交 job → 选择 `train.py`/`train_async.py`
> 2. 入口层（`train*.py`）：`create_placement_groups` 分配 GPU；`create_actor_group` 构建训练 Actor 组；`create_rollout_manager` 构建推理/数据生成管理器
> 3. 执行层（`ray/`+`backends/`）：`actor_group.async_train(...)` → Megatron 梯度计算；`rollout_manager.async_generate(...)` → SGLang 批量推理；`actor_group.async_update_weights()` → 将训练权重推送到推理引擎
> 4. 数据流（`buffer.py`）：`Buffer` 抽样/拼批/调用生成 → 返回训练样本

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
   > 在 KV cache 被 release 之后，tensor 仍保留，只是 virtual address 映射的物理内存被释放；与此
   > 同时 radix tree 仍索引着整个 KV cache。当 resume 之后物理内存上的旧 KV 已不存在，且模型参数也
   > 被更新——出于这两点，一定要用 flush cache 接口刷新 radix tree 索引。

   Other side effects to watch for: version-number bump, the lock that prevents concurrent
   rollout and weight broadcast, resume/pause of the inference engine.

## Pitfalls

- **Vague verbs.** "Processes the batch" hides the mutation. Say allocate/write/update/free.
- **No running example.** Counts ("2 slots", "1 slot") must trace one concrete request.
- **Out-of-order narration.** Follow execution order; if you must reference a later stage,
  link forward, don't reorder.
- **Forgetting "No change" and the side effects.** Both are where readers form wrong mental
  models. State them.
