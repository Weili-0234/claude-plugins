# Analyzing a target repo before writing

Do this reconnaissance before drafting. The targets live under `~/code/ThunderAgent-v2/`
(real upstream trees: `sglang` = sgl-project/sglang, `vllm` = vllm-project/vllm, etc.).

## Pin the commit first

The whole article is anchored to one commit. Capture it before reading anything:

```bash
cd ~/code/ThunderAgent-v2/<repo>
git rev-parse HEAD                 # the commit hash to pin
git remote get-url origin          # -> https://github.com/<org>/<repo>.git
```

Build every link as `https://github.com/<org>/<repo>/blob/<HEAD>/<path>#L<start>-L<end>`.
Line numbers are valid only at that commit — re-derive them from the pinned tree, never copy
from an old article or from `main`. If you analyze across a `git pull`, re-pin and re-check.

## Where the key data structures live

These are stable module locations (line numbers drift — grep within them at your commit).

### SGLang (`python/sglang/srt/`)

| structure / role | file |
|---|---|
| `Req`, `ScheduleBatch`, `ModelWorkerBatch` | `managers/schedule_batch.py` |
| `ForwardBatch` (low-level GPU tensors) | `model_executor/forward_batch_info.py` |
| `req_to_token_pool`, `token_to_kv_pool` (KV pools) | `mem_cache/memory_pool.py` |
| `tree_cache` / RadixCache (prefix reuse) | `mem_cache/radix_cache.py` (+ `base_prefix_cache.py`) |
| Scheduler event loop, batch forming, result processing | `managers/scheduler.py` (+ `schedule_policy.py`) |
| TpModelWorker (`forward_batch_generation`) | `managers/tp_worker.py` |
| TokenizerManager / DetokenizerManager / I/O structs | `managers/tokenizer_manager.py`, `detokenizer_manager.py`, `io_struct.py` |
| ModelRunner (`forward`, weight load) | `model_executor/model_runner.py` |
| attention backends (`forward_extend`/`forward_decode`, `save_kv_cache`) | `layers/attention/` |

Canonical lifecycle spine: Server → `TokenizerManager.generate_request` →
`Scheduler.event_loop_normal` (`recv_requests`→`get_next_batch_to_run`→`run_batch`→
`process_batch_result`) → `TpModelWorker.forward_batch_generation` → `ModelRunner.forward` →
attention backend → `DetokenizerManager` → back to Server.

### vLLM v1 (`vllm/v1/`)

| structure / role | file |
|---|---|
| `Request` (engine-side request state) | `request.py` |
| Scheduler + `SchedulerOutput` | `core/sched/scheduler.py`, `core/sched/output.py` |
| KV cache manager / block pool / coordinator | `core/kv_cache_manager.py`, `core/block_pool.py`, `core/kv_cache_coordinator.py` |
| KV cache spec/interface, block table | `kv_cache_interface.py`, `worker/block_table.py` (+ `worker/gpu/block_table.py`) |
| EngineCore loop, LLMEngine, AsyncLLM | `engine/core.py`, `engine/llm_engine.py`, `engine/async_llm.py` |
| input processing, detokenize, output | `engine/input_processor.py`, `engine/detokenizer.py`, `engine/output_processor.py` |
| GPU model runner | `worker/gpu_model_runner.py` (under `worker/`) |

vLLM v1 uses **paged blocks** (block_pool + block_table) rather than SGLang's two-level
token pools — a natural contrast to draw if you've written the SGLang version.

### slime (RL framework; SGLang rollout + Megatron training)

| structure / role | file |
|---|---|
| `Sample` (rollout↔train unit), `RolloutController`, `_convert_samples_to_train_data` | `slime/ray/buffer.py` |
| placement groups / GPU mapping | `slime/ray/placement_group.py` |
| training + rollout backends, weight push | `slime/backends/` |
| entry points | `train.py`, `train_async.py`, `scripts/` |

### verl (RL framework)

| structure / role | file |
|---|---|
| `DataProto` (universal exchange object) | `verl/protocol.py` |
| `RayPPOTrainer` (`fit()` training loop) | `verl/trainer/ppo/ray_trainer.py` |
| SGLang rollout, `AsyncRolloutRequest`, `AsyncEngine` | `verl/workers/rollout/sglang_rollout/sglang_rollout.py` |
| FSDP↔SGLang weight bridge | `FSDPSGLangShardingManager` (workers/sharding manager) |
| dataset / collate | `verl/utils/dataset/` |

For Megatron-based training internals (gradient/optimizer/weight gather) treat at the
"understand-reproduce" depth — explain mechanism and the interface that crosses to the
inference engine; don't deep-dive kernel internals unless that's the article's subject.

## Grep recipes

```bash
# class / dataclass definitions of a structure
grep -rn "class ScheduleBatch\|@dataclass" python/sglang/srt/managers/schedule_batch.py

# who ALLOCATES / FREES (the lifecycle endpoints)
grep -rn "alloc\|free\|out_cache_loc\|cache_finished\|cache_unfinished" python/sglang/srt/mem_cache/

# who WRITES a field of the exchange object (the data-growth chain)
grep -rn "batch\.union\|batch\.pop\|batch\.batch\[" verl/trainer/ppo/

# who mutates a structure (assignments to self.<field>)
grep -rn "self\.req_to_token\|self\.token_to_kv" python/sglang/srt/

# follow a call: find definition then callers
grep -rn "def forward_batch_generation" python/sglang/srt/
grep -rn "forward_batch_generation(" python/sglang/srt/

# cross-component weight transfer
grep -rn "update_weights_from_tensor\|flush_cache\|named_tensors\|broadcast" python/sglang/srt/ verl/
```

To trace a lifecycle: find the structure's class, grep its allocation site (start of life),
grep assignments/mutations (the middle), grep its `free`/release/`del` (end of life). The set
of functions that show up is your per-stage section list.

## Method recap

1. `git rev-parse HEAD` → pin the commit; get `<org>/<repo>` from the remote.
2. From the table above, open the files for your subsystem; read the structure definitions.
3. Grep allocate/write/free sites to assemble the function→mutation list (execution order).
4. Verify field names/shapes against the source — don't trust memory or tech reports.
5. Build the spine list, then the per-stage sections, with permalinks at the pinned commit.
