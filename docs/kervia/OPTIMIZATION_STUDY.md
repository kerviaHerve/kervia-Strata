# Dual NVIDIA optimization study

Date: 2026-10-07. Status: source inspection and analysis of historical measurements; **no new GPU experiment and no validated fork speedup**.

Inspected fork baseline: `3c10ad41fd6b8cc56cce463244f79727b35846be`. Engine baseline: upstream `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253` (`v0.1.40.1`). GitHub's upstream `main` resolved to that same engine revision during this study. `git diff` confirmed that `src/`, `include/`, `serve/`, `CMakeLists.txt` and `tools/make_profile.py` were unchanged between those revisions.

The objective remains a faster single coding agent on two RTX 5070 Ti 16 GB cards, with the complete IQ3_XXS expert set, native images, reliable tools and 131,072 tokens of total context. Every proposed experiment below has an observable input change and a result to measure. **No expected gain, extrapolated percentage or assumed bottleneck is used to select a winner.**

## Evidence and its limits

Live inspection confirmed two RTX 5070 Ti cards, PCIe link widths x8 and x4 and one CPU NUMA node. Both GPUs were idle at the inspection instant; that is not an inference utilization measurement. Link speed had dropped to Gen 1 at idle; the earlier loaded link measurements below are separate evidence. The configured service remained active, with the same PID and restart count throughout the study.

The current prepared profile specifies automatic layer placement, one active request, MTP length 4, draft confidence threshold 0.5, French draft vocabulary, INT8 KV with 32,768 resident tokens, 1,024 MiB reserve per GPU and six conversation checkpoints. It does not request stage-weight trimming or pipelined decode windows. The historical benchmark disabled conversation checkpoints.

The [published historical reference](../../bench/results/kervia/2026-10-07-reference.json) and its retained private engine log provide these observations:

| Observation | Recorded result | Limit |
| --- | --- | --- |
| Client decode | 130.92 tokens/s median, 129.6–133.6 across three outputs of 768 tokens | Three different French prompts, not three repetitions of each prompt; not the new English workload |
| Uncached first content | 9.18 s at 32,030 input tokens; 30.49 s at 120,029 | Retrieval probes; not a long-context agent evaluation |
| Host-to-device probe | 28.9 GB/s on the first GPU; 14.5 GB/s on the second | Startup burst probe, not concurrent application bandwidth |
| Selected split | 21 / 27 layers | One observed automatic placement, not an optimum established by a sweep |
| Resident expert entries | 5,022 + 4,891 = 9,913 | Entry sizes vary; 9,913 / 24,576 is a count, not a routing hit rate |
| Prompt buffers | 8,192-token maximum chunk; 4.12 GiB borrowed from each GPU's cache | Buffers are lent and refilled; not permanently lost memory |
| Process memory | About 46.3 GiB RSS; about 15,175 / 15,182 MiB total GPU usage | GPU values include desktop use; RSS is not the cgroup total |
| Draft acceptance on the three 768-token requests | 495/644, 469/630, 477/624 = 76.86%, 74.44%, 76.44% | Includes the engine's reported speculative drafts; not an independent pure-MTP quality score |
| Model loading plus first response | 46.88 s in one start, 83.88 s in another | Different cache conditions/first responses; not an A/B result |

The expert counters need a consistent denominator. In `src/program/generate.cpp` around line 10011, the displayed hit rate excludes experts offloaded over PCIe from its denominator. Recalculation from the retained log gives:

| Historical request | Resident hits / all routed | Offloaded / all routed | Remaining CPU work / all routed |
| --- | ---: | ---: | ---: |
| 48 input tokens, 768 output | 397,284 / 440,640 = 90.16% | 12,335 / 440,640 = 2.80% | 7.04% |
| 49 input tokens, 768 output | 407,938 / 446,400 = 91.38% | 10,409 / 446,400 = 2.33% | 6.28% |
| 47 input tokens, 768 output | 403,352 / 440,160 = 91.64% | 9,902 / 440,160 = 2.25% | 6.11% |

The remainder is `(lookups - hits) / (lookups + offloaded)`. This is a share of expert operations, **not a share of elapsed time**. It does not justify predicting a proportional speedup from eliminating that work.

## 1. Make the comparison and profiling trustworthy

**Verified:** `tools/kervia_bench.py:110` performs one warmup and one call for each of three topics. It records client streaming times, but not per-GPU stage times, repeated trials per input, image/tool checks or long-context generation. Its median mixes different prompts. This is a useful starting client, not yet the complete optimization harness.

**Verified:** `src/core/verify.cpp:1096` and `:1295` require `!prof_on_` to overlap the shared expert on another stream. `STRATA_VERIFY_PROFILE=1` therefore changes the execution schedule. A detailed profile can help locate work, but its measured throughput cannot stand in for the normal path.

**Verified:** `src/program/generate.cpp:10045` reports cumulative stage timing, while the KV counter reporting at `:10055` walks the first stage's `ss` only. KV maps can reset on state reset/restore (`src/core/layer.cpp`, `src/core/conversation_snapshot.cpp`). These counters cannot be treated as both GPUs' per-request totals without explicit snapshots and reset handling.

**Fork work to evaluate:** a run manifest, repeatable replay workload, per-stage/per-request counter deltas, both GPUs' KV statistics and timing scopes that preserve stream dependencies. Retain the current diagnostic mode but label its scheduling change. Capture the effective settings and disabled-feature reasons, not just the requested config.

**Measure:** A/A repeatability first; measurement overhead with telemetry off/on; client TTFT and decode separately from engine timing; actual output length; per-GPU memory, waits and transfer bytes; correctness outcomes. Diagnose with instrumentation and confirm any speed claim in uninstrumented paired runs.

## 2. Remove duplicated dense weights where supported

**Verified:** the default split loads a full dense-weight copy on each card. `--trim-stage-weights` / `STRATA_STAGE_TRIM=1` already exist upstream (`src/program/generate.cpp:2521`). With an explicit boundary, both stages can load only their own layer ranges. With `auto`, the first GPU is loaded before the boundary is known and remains untrimmed; later GPUs can be trimmed after placement (`:3373`). The current documentation is less precise about this automatic case than the code.

**Controlled first test:** compare explicit K=21 without trim against explicit K=21 with trim. Keep the device order, context, model, draft, cache reset policy and all other flags fixed. Compare `auto` with explicit K=21 separately and verify that the effective cache sizes actually match; do not attribute a placement change to trimming.

**Measure:** actual per-card allocated bytes before/after weight loading, expert slots and resident hit counts, prompt peak VRAM, decode time and 32K/120K latency. Check images, tools and generated-code behavior because a different CPU/GPU expert assignment can change rounding.

**Possible fork extension after that test:** choose the split before loading the first GPU's layer-specific weights, or introduce a two-pass metadata planner. Preserve PLE tensors, routers required for lookahead, head/draft ownership and all setup/restore paths. The existing upstream trim option itself is not a new fork invention.

**Status:** memory and speed effects on this machine are unmeasured.

## 3. Replace estimated placement costs with measured inputs

**Verified:** `src/program/generate.cpp:3060–3234` uses a cost model calibrated on another GPU pair. Layer cost scales as SM count × nominal clock; the default miss coefficient is 190 ms. On two GPUs the expert-frequency surrogate remains `(rank + 1)^-1.2`, unless explicitly overridden. A single miss coefficient is used, although the per-card transfer probes differ.

Both cards received the same 0.40 ms/layer estimate in the historical log. In that formula, their summed layer term is constant for all boundaries: `K*c + (48-K)*c = 48*c`. The choice then depends on estimated cache coverage, rather than a measured difference in their stage durations. This mathematical property does **not** establish that K=21 is wrong.

**Verified:** `tools/make_profile.py` reads routing counts but writes a ranking without those counts. With the complete shipped base and no `--reorder`, traces cannot change that ranking. Learned-profile persistence also already exists (`--expert-profile-save`, `src/program/generate.cpp:7056`); adding generic persistence would duplicate upstream functionality.

**Controlled tests:** first compare explicit K=19, 21, 23 and 25 with the same trim setting and GPU order. Repeat the selected boundary and an adjacent boundary on holdout inputs. Test reversing GPU order in a separate experiment; the display memory and x8/x4 paths must remain associated with their actual physical devices.

**Fork work to evaluate:** preserve measured routing frequencies in a versioned sidecar with model/workload identity; calibrate per-stage time and miss/transfer cost; price stage-specific dense weights after trimming. Keep the existing auto selector as the fallback when calibration is absent or stale. Profile inputs must be synthetic/public or explicitly approved private inputs, with a separate holdout workload.

**Measure:** prediction error for held routing mass and stage time, plus observed end-to-end latency. The old 97.4% predicted mass and the historical request hit rates were collected at different cache states; their difference is not by itself a controlled accuracy test.

**Status:** no alternative boundary or measured selector has been validated on this machine.

## 4. Evaluate overlapping decode windows

**Verified:** `--pipeline-windows 2` already overlaps two stages across speculative windows for a single conversation. Without it, the stages process each verify window in turn. This is documented in [upstream's multi-GPU guide](https://github.com/Niko1221/Strata/blob/v0.1.40.1/docs/MULTI_GPU.md) and implemented in `src/program/generate.cpp` around `:2893`, `:6016` and `:9200`.

**Controlled test:** off versus 2 at fixed explicit placement and trim setting. Record the *effective* activation and why it may be disabled. Do not combine it with batch slots, helper caches, peer-device execution or asynchronous expert adaptation. Repetition penalties and coupled draft sampling can select serial execution for an individual request.

The code reserves 160 MiB per GPU for a second verifier and also requires first-stage recurrent-state snapshots. Record actual allocations; do not treat the split search's 96 MiB snapshot estimate as an exact measurement. Include a cache-capacity-matched serial control to separate scheduling effects from changed expert residency.

`--remote-expert-opt` appears in the current prepared config, but its object is created only when helper-cache entries exist (`src/program/generate.cpp:4212`). With two cards both used as stages and no helper caches, that flag alone neither demonstrates a speed feature in use nor trips the actual helper-cache pipeline exclusion.

**Fork work only if measurements justify it:** report accepted versus discarded speculative windows and idle time per stage; then evaluate a measured activation policy. The pipeline mechanism is upstream functionality.

**Measure:** completed output time, decode rate, window guesses kept/discarded, stage overlap, MTP acceptance, cache size, memory peaks and rollback/cancellation correctness. Test actual agent sampling parameters as well as greedy controls.

**Status:** no local pipeline speedup is established.

## 5. Measure prompt processing and cache refill separately

**Verified:** `--prefill auto` chooses chunks by buffer fit, up to 8,192 tokens in the historical run. Prompt buffers borrowed 4.12 GiB from each card's expert cache. `STRATA_PREFILL_HELP=1` can make the idle stage help a one-chunk prompt, on the native MMQ path; the default sharing function falls to zero from 3,277 tokens (`src/prefill/prefill.cpp:1252`: `0.5 - T/16384` must be at least `0.3`). `STRATA_SPLIT_OWN` separately controls dedicated rather than borrowed buffers.

**Controlled tests:** 4,096 versus 8,192 maximum chunk size on long prompts; helper off/on for approximately 1K, 2K and 3K prompts, with controls at and above the 3,277-token boundary. Evaluate owned versus borrowed buffers only in a separate memory-matched experiment. Do not enable all options together.

**Measure:** uncached TTFT, time spent in expert copies, host grouping and post-prompt refill, per-card peak memory, and decode performance after refill. Use `STRATA_PREFILL_TIMING` for diagnosis, then repeat without it. The helper's row grouping can change rounding; functional checks remain mandatory.

**Possible fork work after measurement:** choose chunk size and helper share from calibrated stage/copy times rather than free space and one fixed sharing curve.

**Status:** no prompt-processing alternative has been measured locally.

## 6. Treat MTP, expert caches and KV as coupled budgets

**Verified:** MTP is already enabled, and a draft-confidence threshold already shortens verification windows. Suffix drafting also already exists. The historical acceptance counts are above; they do not tell us the cheapest draft length. INT8 KV and a 32,768-token resident window are active, with additional context backed by host RAM.

**Controlled tests after the placement/pipeline results:** MTP lengths 2 and 4 first; test other supported lengths only after recording the actual window limit and acceptance cost. Keep vocabulary, thresholds and suffix settings fixed initially. For KV, compare 32,768 and 65,536 resident tokens while preserving the same 131,072 total context and INT8 format. Measure both cards' counters; current first-stage-only reporting is insufficient for that decision.

For cache ranking, compare a synthetic training-derived profile against the shipped profile on disjoint code, French text, image and tool workloads. Start each paired run with the same cache state or explicit replay history. An adaptive cache means `--prompt-cache 0` alone does not produce equivalent initial expert placement.

**Measure:** milliseconds per accepted token including draft and rejected work; full response time; KV miss bytes, expert misses, available RAM and cgroup usage; holdout functional results. Additional KV residency displaces other allocations, so no standalone hit-rate improvement is accepted as a speed result.

**Status:** no selected alternative. More speculative tokens, more KV residency or a warmer expert cache are not automatically faster.

## Lower-level work requires a measured hotspot

The build already targets SM120, uses CUDA graphs and native quantized kernels. Adding those labels is not an optimization. Candidate kernel locations include `src/kernels/cuda/native_mmvq.cu`, `native_moe.cu`, `iq_kernels.cu` and the QSA kernels, but no current per-kernel timing establishes which deserves a patch.

The [NVIDIA Blackwell tuning guide](https://docs.nvidia.com/cuda/blackwell-tuning-guide/index.html) distinguishes compute capability 12.0 from 10.0. A B200-specific memory or occupancy claim must not be copied onto these GeForce cards. Use [Nsight Systems](https://docs.nvidia.com/nsight-systems/UserGuide/index.html) for scheduling/transfer investigation when available, then kernel profiling only on an identified hotspot. No profiler was installed or launched during this study.

A proposed kernel change needs a representative microbenchmark, numerical/parity checks and an application-level A/B result. Do not start with tensor-parallel rewrites, quantization changes, expert pruning, reduced context, overclocking or system-memory tuning: none has measured evidence here as a way to improve this fork while preserving the requested behavior.

## Bounded measurement sequence

This is an experiment specification, not a claim that the experiments ran.

1. **A/A baseline:** same binary/config, three repetitions of each fixed input; at least two independently initialized/replayed sessions. Identify warmup, graph capture, adaptive expert state and prompt-cache state separately. Collect the effective runtime manifest.
2. **Trim:** fixed K=21, off/on; compare memory allocations and latency. Keep auto-versus-explicit as a separate control.
3. **Placement:** K=19/21/23/25 under one fixed trim policy; retain the best *measured* candidate, then validate on holdout inputs and adjacent boundaries.
4. **Pipeline:** off/2 on the retained explicit placement; add the equal-cache serial control. Test cancellation, prefix restoration and request-level fallback conditions.
5. **Prompt/KV/MTP experiments:** one variable at a time only after the earlier results identify the relevant cost. Run a final combined candidate against the untouched baseline; individual gains cannot be added together.

The initial screening budget is at most 12 distinct engine configurations and three repetitions per input. This is a search bound, not a statistical guarantee. If a difference remains inside baseline variability, report **inconclusive**; obtain more samples within a separately documented extension rather than declare a winner. Do not report a useful p95 from three requests. A latency-distribution claim needs a larger, predeclared replay sample.

Every retained candidate must pass the same release gate: code execution in isolation, native image OCR/shapes, multi-step and streamed tools, uncached 32K and near-128K retrieval **and sustained generation**, cached continuation, cancellation/recovery, per-card memory peaks and no OOM. Keep input plus output within 131,072 tokens. A gate pass covers its cases, not general model-quality equivalence.

Report paired elapsed-time ratios for identical inputs/output limits; preserve early-EOS and failure cases rather than silently dropping them. Engine decode and SSE client decode are separate metrics. Choose a winner only after repeated improvement beyond observed run variation and the correctness/memory gates. Otherwise retain the baseline.

## Documentation and rollback

Follow the [required change record](../../CONTRIBUTING.md#required-change-record). Every implementation/experiment must identify its parent baseline, exact change, reproduction commands, raw-result hashes, counter definitions, failed variants and rollback. Keep synthetic/public summaries in Git; private traces, model files and generated configs stay outside it.

**This change:** added this study and strengthened the contribution/agent instructions to require that record. Validation: source/config inspection, recomputation of historical counters, relative-link and whitespace checks. No performance test is claimed. No engine/server/profile source, model weights or production settings were changed, and no service was restarted. The documentation work is on a dedicated local branch; no publication was performed. Rollback consists only of reverting these documentation changes; production needs no rollback.
