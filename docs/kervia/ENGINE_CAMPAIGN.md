# Engine campaign: four independent changes

Status: completed on 2026-10-07. Four changes implemented and measured. Only shared-prefix borrowing has a repeated latency benefit on the reference workload; the other three remain experiments. Production is not deployed from this campaign.

## Reference and scope

The parent is `ac8b0ab45282a179355c0d0bd9d6f14c3679e663`, engine upstream
`82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`. Use the already measured K25/23,
trimmed stage weights, two-window pipeline profile throughout. This campaign
must not credit the engine changes for that earlier configuration gain.
The full IQ3_XXS model, 131072-token context, INT8 KV, 32768 resident KV tokens,
MTP4 and sampling settings remain identical. Production binaries and configuration
stay separate. The workstation has another GPU-resident process; measurements
describe this shared host, not an otherwise isolated machine.

## Predeclared experiments

| Change | Source / hypothesis | Measurement and correctness |
|---|---|---|
| 1. Grouped short prefill | Upstream PR1107, `8e216160d79ea290464310563197b0571244e5bc`; fewer gather launches for fewer than 1024 new tokens | Cold and cached continuations at several lengths: TTFT, engine prefill milliseconds, unchanged output checks, extra VRAM |
| 2. Stale lookup costs | Upstream PR1316, `8e0a7b36ec2a427f879b218b354cde2fdf4487a2`; bounded remeasurement after a slow estimate | Deterministic stale-cost recovery test plus repeated GPU decode/lookup workloads; tokens/s and offered/accepted drafts |
| 3. Adaptive pipeline gate | Fork experiment: observed probability calibration and measured stage cost | Fixed gate versus adaptive gate: tokens/s, speculative launches, successes, rollbacks, content/function checks |
| 4. Shared prefixes on split GPUs | Upstream PR1164 `2a30c0456979c246aee9f8f7c5786dc6b524ddc2` and dependency PR1163 `ed63fa81c2d5919d8a4c4629e1345feabe295463`, extended by this fork | Alternating sibling conversations: reused tokens, TTFT, retained cache bytes, prefix integrity, all-stage validation before writes |

Each experiment is opt-in, independently selectable, and compared with the same
disabled path. Budget: four isolated candidates, one combined candidate, and up
to three corrective candidates if a correctness failure is found. At least three
repetitions per synthetic timing workload; repeat reference and retained candidate.
Keep every failure and rejected variant. Long-context, vision, code execution,
streamed tool calls and cancellation qualify a retained combination. No raw user
conversation is used. No benchmark timing runs during compilation.

The four flags are `STRATA_SHORT_GROUP_GATHER=1`, `STRATA_LOOKUP_REPROBE=1`,
`STRATA_PIPELINE_ADAPTIVE_GATE=1` and `STRATA_CONVERSATION_BORROW=1`. Leave them
unset for the disabled control. The lookup class keeps upstream's corrected
default for its standalone tests; the serving and CLI engines explicitly disable
it unless the experiment is selected. Borrowing supports both single-device and
split-device sessions. It uses the draft KV on the **last** stage of a split.

The engine candidate is `3b708ee9ccba45aec358543dda27f0811b366526`. Later harness,
CI and documentation commits do not change its binary. Independent controls use
this same binary with every experiment disabled, including the imported buffer
capacity dependency, so that dependency is not credited to a particular flag.

## Workloads and controls

The fixed `kervia-engine-agent-v2` sequence in `tools/kervia_engine_bench.py`
contains three repetitions of cold prompts of 131/417/797 API tokens, three
sizes of continuation below 1024 newly read tokens, and three sibling cycles.
Continuations use fixed synthetic assistant turns, so **request payload hashes
must match across candidates**, independently of generated responses. Each
sibling cycle is A, unrelated conversation, B sharing A's system prefix, then
A again. Return prompts contain 4733 tokens. The private branch marker must be
recovered without the other branch's marker. This measures sequential interleaving,
not concurrent multi-client serving or an actual Hermes/Privy session.

The decode suite retains the earlier three prompts, three replays, 768 output
tokens, temperature 0.6, top-p 0.95, top-k 20, min-p 0 and seed 42. Cache workloads
are greedy, seed 42, maximum 96 output tokens; early stops remain in the raw
results. Each engine starts fresh with the same expert profile and a warmup.
Adaptive expert placement stays enabled. Response hashes are recorded; this is
not a claim of bitwise equivalence or a general agent-quality evaluation.

Uncached sessions have `--prompt-cache 0`. Cache sessions use six checkpoints,
`--conversation-cache-mib 2048`, four parked slots and the unchanged 2560 MiB
physical-memory floor. This is a bounded RAM cache, not unlimited sharing of
128K-token conversations. Oversized images must fall back to normal processing.

The definitive trials use cgroup MemoryHigh=51G, MemoryMax=52G, MemorySwapMax=0,
900-second trial timeouts and one-second resource sampling. An early 48G-soft-limit
decode trial recorded eight memory-high events; an early cache trial recorded
2643. Their timings are excluded. A subsequent screening startup was interrupted
to align limits before comparisons. The early cache fixture also depended on a
generated assistant reply; v2 removes that input-shape bias.

A helper CLI indentation error stopped the second supervisor after the definitive
decode reference had completed and recovered the API, before the next trial
started. It was corrected and syntax-checked. The final systemd recovery hook
uses a separate standard-library-only script, independent of repository imports.
Artifacts from failed preparation and interrupted/excluded trials remain private.

All definitive trials enable `STRATA_DECODE_TIMING=1` for the existing host-side
aggregate counters. `STRATA_VERIFY_PROFILE` is **not** enabled: that detailed
profiler changes shared-expert scheduling. Host-observed policy timestamps add
no GPU waits. Sampled resource peaks include vision and other resident processes;
they are not allocation-exact. Small differences need repeated confirmation.

## Build and replay

Both binaries use GCC 15.2, CUDA 13.2.86, Release (`-O3 -DNDEBUG`), SM120 and the
same locally prepared llama.cpp/ggml sources. All recorded CMake option values
match. No compiler, driver, library or model is installed or upgraded.

```bash
git worktree add --detach ../strata-engine-reference ac8b0ab45282a179355c0d0bd9d6f14c3679e663
cmake -S ../strata-engine-reference -B ../build-engine-reference -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DSTRATA_BUILD_TESTS=OFF -DSTRATA_BUILD_CONVERSATION_TESTS=ON \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DSTRATA_GGML_DIR="$GGML_SOURCE"
cmake --build ../build-engine-reference --target strata --parallel 4
# Repeat with this checkout as -S and a separate candidate build directory.
```

`NVCC` and `GGML_SOURCE` identify the same existing toolkit and ggml tree for both
builds. The local campaign explicitly selected the prepared Ninja executable.
Keep build jobs separate from GPU timing. Binary SHA256 values:

- Reference: `9d459c9e395b45a89d83c635196824fdba7c8b07470af34171d856810b1364d7`.
- Candidate: `727bedc2f24c7325cccea6411adccf33c4d0f46f1a1b3c5f5eed6db8d701e422`.

Generate a private configuration using the already measured profile, preserve
the model/tokenizer/vision paths, and explicitly select the appropriate **newly
built** engine executable. Add the cache budget/slots above for cache sessions.
The previous upstream executable does not implement these experiment flags.
Start a separate loopback server with one selected flag (or all four for the
combination), for example:

```bash
STRATA_DECODE_TIMING=1 STRATA_CONVERSATION_BORROW=1 \
  .venv/bin/python serve/server.py --engine strata --config experiment.local.json \
  --host 127.0.0.1 --port 18080
.venv/bin/python -m tools.kervia_engine_bench \
  --base-url http://127.0.0.1:18080/v1 --output cache-results.local.jsonl
```

For decode sessions, use the exact commands and gate sequence in
[FIRST_CAMPAIGN.md](FIRST_CAMPAIGN.md), now with the two newly built executables
and the same optimized profile. Final confirmation adds the existing three-prompt
holdout and cancellation. Cache confirmation runs the v2 workload first, followed
by functional gates, two identical 32K requests, a 120K request and cancellation.
The private supervisor records every command, config hash, binary hash and sample.
`tools/kervia_engine_report.py` exports allowlisted numeric results and synthetic
digests; command lines, host paths, credentials, process IDs and raw logs stay local.

CPU policy recovery can be reproduced with each checkout's include/source paths:

```bash
g++ -std=c++20 -O2 -I include bench/fixtures/kervia/policy_recovery.cpp \
  src/spec/draft_policy.cpp -o policy-recovery
./policy-recovery
```

The 1000/40/44 ms values are supplied synthetic costs, not GPU timings. Run the
seven C++ CPU tests and Python checks from [CONTRIBUTING.md](../../CONTRIBUTING.md).
`conversation_snapshot_test` separately requires a GPU; each card passed 4097
checks, covering KV formats, storage modes, prefix bytes, checkpoint state,
untouched donors and the stage-local restore API. Actual split-device borrowing
is additionally checked by the two-GPU sibling workload.

## Provenance and rollback

The four upstream commits are cherry-picked with `-x` and original authors.
The cache buffer capacity change is recorded as a dependency, not a fifth speed
claim. Results must separate this memory change from preservation of sibling KV.
Restore the parent engine binary and reference configuration for rollback;
experimental flags default off. Runtime experiments use a private loopback server
and a supervisor that restores the original local API after success or failure.

## Adaptive policy definition

The new gate uses decayed successes from every scored next window, including
windows rejected by the gate, to reduce selection bias. It retains the fixed gate
until 32 outcomes, eight effective observations in a probability bin, and three
stage timing samples for both relevant window sizes. With calibrated probability
`p`, it launches if `p * min(stage0_ms, stage1_ms) > (1-p) * stage0_ms`.
This is a testable scheduling heuristic, not a measured counterfactual savings
formula. Stage times are host-observed asynchronous completion intervals; no CUDA
synchronization or verifier profiling is added. The verifier still determines
every emitted token. All policy state resets for each request.


## Results and decisions

[All numeric trials, digests and resource summaries](../../bench/results/kervia/2026-10-07-engine-campaign.json)
include **14 definitive sessions**, two excluded exploratory sessions and the
preparation failures. Every definitive session has zero memory-high, memory-max,
OOM and cgroup-swap events, and no telemetry collection errors. There were seven
cache sessions of 33 measured requests each; their request payload hashes match
position for position and every marker check passes. Nine 768-token decode
requests per decode session all reached the limit without prefix reuse.

The first three rows use the same fork binary with all flags disabled as their
control. The fourth is also repeated against the original reference build.
Numbers are medians of three repetitions unless described as totals.

| Change | Before | After | Decision |
|---|---|---|---|
| 1. Grouped short prefill | Cold 131/417/797-token TTFT: 0.790 / 1.002 / 1.368 s | 0.786 / 1.009 / 1.356 s | No established gain; remain opt-in |
| 1. Cached continuation, three sizes | TTFT: 0.711 / 1.103 / 1.529 s | 0.700 / 1.106 / 1.527 s | No established gain; cache reuse itself also varies slightly on the shortest case |
| 2. Stale lookup recovery | Synthetic full window selected 0/256 times, stale supplied cost 1000 ms retained | 192/256 selections, first retry at zero-based index 64, fresh supplied cost 44 ms retained | Recovery behavior verified; no repeatable GPU speed gain established |
| 3. Adaptive pipeline gate | 1435 rollbacks / 2266 speculative launches; total reported pipeline time 45,842 ms over nine requests | 545 / 1144; total 45,865 ms | 62.0% fewer rollbacks, essentially unchanged total pipeline time; not promoted as faster |
| 4. Sibling A resumed after B, screening | 1.950 s, 3056/4733 input tokens reused | 0.382 s, 4682/4733 reused | Clear improvement; retain as an opt-in agent-cache option |
| 4. Independent confirmation against original engine | 1.954441 s, 3056/4733 reused | 0.377503 s, 4682/4733 reused | **80.685% lower first-token latency (5.18x shorter)** on this scenario |

The recovery fixture's two cases use cap/MTP pairs 4/2 and 6/4 and produce the same
0-to-192 result. Those costs are synthetic inputs. They are not measured round
latencies or a GPU speedup. On the GPU suite, the pooled decode median is
149.82 tokens/s with all flags disabled, 151.25 with lookup remeasurement, and
154.36 with the adaptive gate. These small differences do not justify promotion:
the original reference itself changes from 159.04 to 150.96 tokens/s between its
two definitive sessions. Per-prompt results and all outputs remain in the JSON.
For the gate, the nine-request pipeline total gives particularly clear evidence
that fewer rollbacks are not automatically less elapsed time.

Why the retained cache change helps: B previously **took** A's parked snapshot
when matching A's shared system checkpoint, then overwrote A's later KV. Returning
to A reread 1677 input tokens. Borrowing copies the shared prefix while preserving
A's donor snapshot; returning to A reads only 51 tokens. Both stages and the draft
ring are restored, and the ALPHA/BETA markers stay separate. B's own median TTFT
in confirmation is 1.929 versus 1.948 s; the benefit is preserving A for its return,
not a claim that every request becomes faster.

The all-four combination also passes the full cache/functional/context lifecycle
checks. Its pooled decode median is 151.35 tokens/s and its nine-request pipeline
total is 45,361 ms. It does not establish an advantage over borrowing alone, so
combining all flags is not the recommended outcome. All flags remain off by
default; only `STRATA_CONVERSATION_BORROW=1` with the measured bounded RAM cache is
retained in this runbook for the sequential agent workload.

### Confirmation and correctness

- Local Python: 27 fork tests and 31 upstream tests. Seven standalone C++ CPU
  executables pass locally and in CI on Python 3.11/3.12 jobs. CUDA Release build
  succeeds. `conversation_snapshot_test` passes 4097 checks on each physical GPU.
  This is the selected suite, not all upstream CUDA kernel tests or an AMD test.
- Every functional suite passes generated-code execution with six assertions,
  native synthetic-image recognition, normal tools and streamed tools. The source
  and answer hashes are published. No broad model-quality score is claimed.
- Uncached reference/retained confirmation retrieves the markers at actual
  31,995 and 119,979 input tokens and generates 768 tokens afterward. The 120K
  first-token times are 24.587 and 24.607 s, respectively. The configured total
  window stays 131,072; image-plus-120K reasoning is not tested jointly.
- Cached confirmation for the original, retained and all-four engines reuses
  **31,988/31,995 tokens** on the repeated 32K request and passes the 120K retrieval
  and sustained-generation check. Cancellation recovery takes 1.645 / 1.306 /
  1.393 s, respectively, below the predeclared 30-second bound.
- The retained engine's uncached confirmation differs by -4.52%, +4.69%, +4.11%
  in the three per-prompt decode medians. The additional holdout medians are
  150.70 / 142.74 / 157.32 tokens/s before and 158.90 / 153.12 / 160.96 after.
  The borrow path is inactive in these zero-cache sessions: **do not attribute
  their decode differences to prefix borrowing**. The defensible retained claim
  is the repeated sibling-resume latency result above.

### Memory, operating conditions and limits

Matched cache-confirmation process-tree RSS peaks are **48.841 versus 49.058 GiB**;
minimum available host RAM is **5.379 versus 5.009 GiB**. Both sessions have the
same sampled whole-card peaks, 15,115 / 15,104 MiB. The 2 GiB parking budget and
four-slot eviction policy are unchanged between sides. Additional donor retention
is not free memory. Oversized snapshots can skip parking, and borrowing can fall
back to taking a snapshot when the outgoing conversation fits only in its room.
The cache budget is not a promise to keep several full 128K conversations.

This is an AMD Ryzen 9 7900, two 16 GB RTX 5070 Ti cards in PCIe 5.0 x8/x4 order,
Ubuntu 26.04, driver 595.91.07, 60.96 GiB usable host RAM. A foreign compute process
stays resident. Per-process GPU activity, CPU utilization, energy per request,
thermal throttling, concurrent clients, reversed GPU order, AMD execution and
long-term soak behavior were not measured. GPU peaks can include other activity;
for example one uncached candidate session peaks at 15,485 MiB on card 0. No
isolation or energy-saving claim follows from fewer pipeline rollbacks.

The same local ggml source tree supplies both builds: 1536 source/CMake files,
SHA256 `4da38858f9df81994799b73df9ab5dd82ff5d2a559330183017f2174d61764fb`
(sorted relative path, NUL, then each file's binary SHA256). It is an extracted
tree, not a separate Git checkout; setup pins llama.cpp to
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. Model and build identities are included
in the result record. The prepared MTP is unchanged.

## Retained option and rollback

For this machine and the tested interleaving pattern, build the candidate engine,
generate a **new private** config from the measured K25/23 profile, select that
binary in `exe`, and set these options in the copy:

```text
--prompt-cache 6
--conversation-cache-mib 2048
--conversation-cache-slots 4
```

Launch that experiment copy with `STRATA_CONVERSATION_BORROW=1` and leave the other
three experiment variables unset. Inspect the `conversation cache: borrowed`
log and actual API cached-token usage to establish activation. The environment
flag alone does not enable the RAM cache, and the profile generator does not
replace the installed executable. The replay command above reproduces the
workload. This is documented for an explicitly selected experiment; production
was not switched or deployed.

Runtime rollback: stop the experiment server and start the untouched original
prepared service/configuration. In the new engine, unsetting the borrow flag
restores the take-whole behavior; `--conversation-cache-mib 0` disables RAM parking.
For full engine rollback use the reference binary/source revision above, which
also removes the imported buffer-capacity change. Repository rollback is a revert
PR, not a destructive reset. Original service recovery, config/binary hashes,
local API health and disappearance of the trial listener are verified separately
in the private completion record. The public PR remains unmerged.
