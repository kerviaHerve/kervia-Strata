# First dual NVIDIA measurement campaign

Parent: `ad52647`. Date: 2026-10-07. The protocol was prepared before the experiments; measured results and limitations are recorded below.

## Scope and provenance

Evaluate upstream's existing stage trimming, explicit placement and pipelined windows on the reference two RTX 5070 Ti cards. Use the exact existing upstream engine binary and unchanged model/draft files for both sides. The server source is unchanged. These are **configuration experiments**, not a claim that a new fork CUDA kernel is faster. Any retained fork profile will identify that distinction.

The prepared production configuration remains unchanged. Experimental copies use a separate loopback port, zero prefix checkpoints and a private output directory. The local LLM API is paused only after an idle check, with restoration in the campaign supervisor's `finally` block and a systemd stop hook. The known image/music/training services were inactive. Confirmation telemetry revealed a separate resident embedding service using 1,998 MiB on the first GPU; it was left running. This is a **shared-workstation measurement**, not a fully isolated GPU experiment. No model download, driver change, global tuning or public listener was introduced. Only reviewed synthetic summaries are published.

## Measurement changes

- `tools/kervia_bench.py`: three repetitions of each existing English prompt by default, per-prompt statistics, repetition indices, output counts and an explicit sequential replay policy. The workload text and sampling stay at `kervia-english-code-v1`; the result schema is version 2. The aggregate historical field remains for compatibility, but paired decisions use each prompt separately. Prefix reuse invalidates an uncached summary.
- `tools/kervia_metrics.py`: numeric-only extraction of startup and request evidence. Expert fractions use **all routed entries**, including PCIe work. Requested settings are compared with observed startup state. Raw logs stay private. No detailed GPU profiler is enabled because it changes the normal shared-expert schedule.
- `tools/kervia_validate.py`: public synthetic code, native image, normal/streamed two-tool loops and near-32K/120K retrieval followed by sustained generation. Generated Python runs through an AST gate and a networkless Bubblewrap sandbox with CPU/address-space limits. Optional dependencies come from the existing Strata environment. No private prompt is used.
- `tests/kervia/` covers the new helpers and profile behavior; `.github/workflows/ci.yml` and `CONTRIBUTING.md` compile all five helper modules. The README, benchmarking guide, roadmap and initial study link this record. The measured profile is separate from the unchanged default profile.

## Predeclared protocol

One warmup, then three complete replays of the same three-topic sequence, 768 output-token cap, unchanged sampling and French draft vocabulary. Expert adaptation remains enabled, so requests are compared by replay index and independent sessions restart the engine from the same shipped expert profile. Prefix checkpoints are disabled. Actual output lengths and early EOS remain visible; equal token caps do not guarantee equal generated lengths.

First run two independent automatic-placement sessions (A/A). Next compare explicit K=21 without and with trimming, then K=19/23/25 with the same trim policy if earlier gates pass. Pipeline off/2 is a separate step on a measured placement. Maximum initial search: 12 distinct engine configurations; extensions require a documented reason. Same shared binary/model/quantization/context for every run; changing GPU placement is never mixed into the trim-only comparison.

Capture client TTFT/decode/total time, output and input token counts, engine prefill/decode/draft counts, expert-routing denominators and observed cache slots. Sample both GPUs' memory/utilization/power/temperature, process RSS, available host RAM, and cgroup memory/OOM counters. Peak measurements are **sampled**, not allocation-exact. Startup, warmup, decode, validation and long-context phases are labelled separately.

Final confirmation additionally uses `bench/fixtures/kervia/holdout-v1.json`: three new English/French coding prompts, three repetitions each, with the same output limit and sampling. This fixture was committed before the final confirmation sessions and was not used to rank the screening candidates. Cancellation and cached continuation are checked with `tools/kervia_lifecycle.py`; cached tests use a separately labelled six-checkpoint configuration. A closed streaming response must permit a successful follow-up within a predeclared 30-second bound, and checkpoint restoration must reuse at least 90% of the repeated input while retaining retrieval and sustained generation.

The profile generator now accepts an explicit layer boundary from 2 through 47, either in a profile or through `--layer-split`. Its default remains `auto`. It rejects inherited trim/pipeline experiments so generating a reference from an already modified config cannot silently preserve them. Use the untouched prepared config as the source.

All screened configurations receive functional checks and uncached long prompts when they load successfully. Repeated baseline/finalist sessions establish confirmation; a single screening session cannot establish a repeatable winner. No useful p95 is claimed from three repetitions. Failed configurations and retries remain recorded. A final comparison must retain 131,072 total context, native vision, tool calls and memory headroom; no alternative is promoted when correctness or uncertainty prevents a decision.

## Reproduction

Run the CPU checks in `CONTRIBUTING.md`, including the new helper tests. Use the existing Strata environment with Pillow, regex, the prepared tokenizer and Bubblewrap available. Create private experiment configs from the untouched prepared source:

```bash
python3 tools/kervia_profile.py --config strata-iq3_xxs.json --benchmark \
  --gpus 0,1 --draft-vocab fr --output baseline.local.json
python3 tools/kervia_profile.py --config strata-iq3_xxs.json --benchmark \
  --profile configs/dual-nvidia-5070ti-128k-measured.json \
  --gpus 0,1 --draft-vocab fr --output candidate.local.json
```

Start **one at a time**, when the GPUs are available. The campaign used a fresh engine process for every session, with a 48 GiB cgroup memory-high threshold, 52 GiB hard limit, no cgroup swap and a 900-second trial timeout. Preserve the prepared asset paths, GPU order and environment; record any other resident GPU processes. Example for the reference (repeat with `candidate.local.json` in a new process):

```bash
.venv/bin/python serve/server.py --engine strata --config baseline.local.json \
  --host 127.0.0.1 --port 18080
```

In a separate terminal, on that experiment server:

```bash
python3 tools/kervia_bench.py --base-url http://127.0.0.1:18080/v1 \
  --model kervia-strata --repetitions 3 --tokens 768 --output benchmark.local.json
```

Then reproduce the final confirmation's remaining requests in their original order. Use the matching private config as the argument and a new output filename; the snippet writes only synthetic outcomes, not config contents:

```bash
.venv/bin/python - baseline.local.json gates.local.json <<'PY'
import json, os, sys
from pathlib import Path
from tools.kervia_bench import request, endpoint, summarize_runs
from tools.kervia_validate import functional, long_gate
from tools.kervia_lifecycle import cancellation_gate
base, model = 'http://127.0.0.1:18080/v1', 'kervia-strata'
config = json.loads(Path(sys.argv[1]).read_text())
result = {'functional': functional(base, model)}
for target in (32000, 120000):
    result[f'long-{target}'] = long_gate(base, model, config['tokenizer'], target)
fixture = json.loads(Path('bench/fixtures/kervia/holdout-v1.json').read_text())
runs = []
for repetition in range(fixture['repetitions']):
    for index, prompt in enumerate(fixture['prompts']):
        run = request(endpoint(base, False), model, prompt, fixture['output_tokens'], None)
        run.update(repetition=repetition + 1, topic_index=index)
        runs.append(run)
result['holdout'] = {'runs': runs, 'per_prompt': summarize_runs(runs)}
result['cancellation'] = cancellation_gate(base, model)
with os.fdopen(os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
    json.dump(result, out, indent=2)
PY
```

For lifecycle checks, generate separate configs **without** `--benchmark` (six checkpoints), restart the engine with `STRATA_DECODE_TIMING=1`, then call `functional(base, model)`, `prefix_gate(base, model, config['tokenizer'])` from `tools.kervia_lifecycle`, and `cancellation_gate(base, model)` in that order. Do not mix these diagnostic timings into the uninstrumented performance results. `long_gate`'s target is a raw-text tokenizer budget; API prompt usage includes the template and is recorded separately.

To reproduce screening, vary only the table's K/trim/pipeline fields in private copies. The untrimmed reference has no `--trim-stage-weights` or `--pipeline-windows`; serial trimmed cases have trim only. `--layer-split` on the generator overrides placement. The matched-cache serial control uses K=25, trim, no pipeline and `--vram-reserve-mib 1302 --vram-reserve-later-mib 1184`. Leave all other options fixed. Every uncached session starts with the same warmup and nine decode requests, then functional and long-context checks; only the two final confirmation sessions add holdout and cancellation.

The local supervisor records exact commands, protected config hashes, binary hashes, source revisions, environment and each sample in a private run directory. Publish only reviewed summaries and the public workload source. API keys, model paths and raw host logs do not belong in Git.

## Results and decision

The initial screening completed with all functional and long-context gates passing. The K=25 trimmed candidate was at the edge of the predeclared split range and led both aggregate decode and long-context TTFT in that screening. Two neighboring boundaries, K=27 and K=29, were therefore added before selecting the candidate for confirmation; this remains within the original maximum of 12 distinct configurations. This adaptive extension is recorded before those two runs. Screening results alone do not select a default.

### Measured configuration search

The [complete sanitized record](../../bench/results/kervia/2026-10-07-first-campaign.json) contains 15 sessions covering 12 distinct configurations, every measured decode request, engine counters and phase-labelled resource summaries. All decode and long-context requests below produced 768 tokens with zero prefix reuse. The first-token columns use 31,995 and 119,979 actual input tokens. The median over nine decode requests is descriptive; per-prompt confirmation follows separately.

| Session | K | Trim | Pipeline windows | Median decode, tokens/s | First token, 32K, s | First token, 120K, s |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| baseline-a | auto → 21 | no | off | 127.34 | 9.183 | 30.594 |
| baseline-b | auto → 21 | no | off | 121.06 | 9.191 | 30.845 |
| explicit21 | 21 | no | off | 127.37 | 9.216 | 30.659 |
| trim21 | 21 | yes | off | 136.86 | 8.739 | 29.178 |
| trim19 | 19 | yes | off | 129.87 | 9.291 | 31.674 |
| trim23 | 23 | yes | off | 141.05 | 8.337 | 27.186 |
| trim25 | 25 | yes | off | 145.37 | 7.717 | 24.389 |
| trim27 | 27 | yes | off | 138.49 | 7.356 | 22.913 |
| trim29 | 29 | yes | off | 132.02 | 7.243 | 23.769 |
| pipe25 | 25 | yes | 2 | 157.63 | 7.744 | 24.511 |
| serial-matched | 25 | yes | off | 144.87 | 7.785 | 24.549 |
| baseline-c, confirmation | auto → 21 | no | off | 126.78 | 9.155 | 30.807 |
| pipe25-b, confirmation | 25 | yes | 2 | 155.25 | 7.752 | 24.482 |

Trimming at K=21 increased observed resident expert-cache slots from 5,022 + 4,891 to 6,359 + 5,667. Freed dense-weight memory was reused by the automatic expert cache; this is not a claim of lower total VRAM use. The pipeline's additional allocations reduced the trimmed K=25 caches to 5,789 + 5,678 slots. A serial control with reserves of 1,302/1,184 MiB produced **exactly those same cache counts**, versus the pipeline's 1,024/1,024 MiB reserves. Its per-prompt medians were 141.21/142.02/149.88 tokens/s, versus 149.93/161.19/158.01 with the pipeline. No memory-high events occurred during either control's decode phase. Long-prompt phases did incur memory-high events; their differences cannot be treated as an isolated pipeline effect.

K=27 gave a faster 120K first token than K=25 but slower short decode. K=29 further reduced 32K first-token time but did not improve 120K latency over K=27. No single split is declared optimal for all workloads. K=25 with two pipeline windows is retained as an **opt-in single-client profile** because it improved all six confirmation decode medians and both uncached long-prompt latencies against the reference.

### Independent confirmation

Each cell is the median of three full 768-token outputs. Gain is `(candidate / baseline - 1) × 100`, computed before rounding.

| Prompt | baseline-c, tokens/s | pipe25-b, tokens/s | Gain |
| --- | ---: | ---: | ---: |
| LRU cache, English | 120.64 | 151.77 | 25.81% |
| Priority queue, English | 126.33 | 155.24 | 22.89% |
| CSV parser, English | 129.26 | 157.90 | 22.15% |
| Holdout JSONL validator, English | 125.46 | 152.45 | 21.51% |
| Holdout pagination, French | 130.18 | 148.47 | 14.05% |
| Holdout async jobs, English | 131.60 | 167.53 | 27.31% |

First-token latency fell from 9.155 to 7.752 s at 31,995 input tokens (15.32%) and from 30.807 to 24.482 s at 119,979 input tokens (20.53%). These are one uncached probe per session and input size, with earlier independent sessions visible above. The engine's median decode rates for the nine initial requests were 126.71 and 155.06 tokens/s, consistent with the separately measured client rates. No confidence interval or p95 is inferred from this sample size.

All 15 sessions passed the generated-code gate (six behavioral assertions), synthetic native-image keyword/OCR gate and normal/streamed two-tool loops. All 13 uncached sessions passed both long-context marker and sustained-generation checks. The vision gate checks expected words; it is not a general visual-reasoning or strict spatial-association score. Retrieval checks marker presence, not general long-context reasoning. Seeded response hashes differ across configurations and sometimes across replays of the same configuration; bitwise equivalence and broad agent quality are **not established**.

Cancellation followed by a correct recovery request took 0.978 s on baseline-c and 1.370 s on pipe25-b, both below the declared 30-second bound. Separate six-checkpoint sessions restored 31,988 of 31,995 input tokens, retained all three markers and generated 768 tokens. Their cached first-token times were 0.137/0.126 s, and cancellation recovery took 0.891/1.022 s. These two lifecycle sessions enabled `STRATA_DECODE_TIMING=1` and are correctness diagnostics, not the main performance comparison. Pipeline counters confirm real speculation and rollback: the two long requests reported 251/253 speculative windows, 84/79 on-path windows and 167/174 rolled-back windows.

### Resources and uncertainty

The final confirmation pair had sampled process-tree RSS peaks of 46.329/46.385 GiB, minimum available host RAM of 8.498/8.410 GiB and whole-card memory peaks of 15,179/15,188 MiB versus 15,117/15,118 MiB. Whole-card values include vision, the desktop and the resident embedding process. Maximum sampled temperatures were 68/58 °C versus 72/61 °C. Six-checkpoint sessions peaked at 46.611/46.671 GiB RSS. These are sampled maxima, not allocation-exact bounds or a long-running soak test.

No session recorded a cgroup OOM, memory-max event or cgroup swap use. Several screening sessions recorded memory-high reclaim events under the shared 48 GiB soft limit (52 GiB hard limit); the JSON preserves their cumulative counts by phase. **Neither final confirmation session recorded a memory-high event.** Sampling produced no recorded collection errors. CPU utilization, thermal-throttling counters and energy per request were not measured. Per-process GPU utilization for the resident embedding service returned unavailable values, so its complete compute inactivity cannot be asserted. Foreign-process presence was collected only in confirmation/lifecycle sessions; earlier process isolation is unverified. These limitations remain part of the performance claim.

### Provenance and retained change

Engine source: `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`, built previously for SM120 with CUDA 13.2.86; NVIDIA driver 595.91.07. Engine SHA256: `e44d2c5b34fd7ef30bf0f9754650eefb258a8bfdbcddef1a45f844401af32110`. Vision binary SHA256: `a50acdfbf1c0b6bb30b5e6160c627f51b0392c0591e9c805ee055b184c739076`. Model: `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`, revision `ed59f92082b1e93c0e96d60a8b11aab089b52f09`, complete IQ3_XXS expert set and unchanged prepared French draft. No new engine was compiled in this campaign; the complete original compiler invocation is not reconstructed here.

Harness commits: `8b823b9` introduced repeated measurements and validation, `cfd41b1` corrected tokenizer loading, and `3e01ccb` added explicit profile placement, the holdout and lifecycle checks. Each trial records its exact full harness revision in the JSON. The engine, server, model, tokenizer and draft assets were shared between reference and candidate. All performance runs used context 131,072, INT8 KV, resident KV 32,768, MTP 4, minimum draft probability 0.5, automatic prefill/expert caches and one active request. `--remote-expert-opt` was inherited, but no remote helpers were configured. Performance runs had no detailed GPU profiler or CPU timing diagnostics enabled.

The retained [measured profile](../../configs/dual-nvidia-5070ti-128k-measured.json) selects K=25, `--trim-stage-weights` and `--pipeline-windows 2`, and keeps six conversation checkpoints unless `--benchmark` is requested. It targets the measured x8-first/x4-second order and prepared French draft. Different topology, available VRAM, language/draft mix, concurrency, reversed GPU order, single-GPU scaling and long-term stability require new measurements. Production keeps its existing configuration. Automatic placement remains the profile generator's default.

## Validation and rollback

The pre-change 16 fork and 31 upstream CPU tests passed. The final local run passed **27 fork tests and 31 upstream tests**, plus compilation of all five helper modules. New checks cover counter denominators, privacy, repeated-input grouping, prefix-cache rejection, isolated generated-code execution and profile preservation of context/vision/assets in both checkpoint modes. GPU checks are reported separately above.

Generating both measured modes from the actual prepared source reproduced the qualified engine options and preserved the engine, tokenizer, vision, GPU order and draft assets. The later-stage reserve default was normalized to 1,024 MiB for this comparison. Both generated files were exclusive, mode 0600 outputs. Production config, engine and vision binary SHA256 values matched all six pre-batch manifests after recovery.

Preparation correction: the first real long-fixture preflight exposed a missing optional `tokenizers` package. The fixture generator was changed to the exact tokenizer implementation used by Strata's server (`tools.strata_tokenizer`), avoiding a new installation and tokenizer differences. The failed preflight happened before any GPU experiment. A known-correct generated-code fixture was also executed successfully in the sandbox.

Rollback: stop the experiment server and start the untouched previous prepared configuration; do not use an already modified config as input to the reference generator. The opt-in profile can also be replaced by a fresh configuration generated from `configs/dual-nvidia-5070ti-128k.json` and the original source config. For repository rollback, revert the campaign commits through a new PR, preserving unrelated history. Experimental services were stopped and the previously active local LLM service restored. Production configuration and binary hashes are checked after the campaign; no measured profile is automatically deployed.
