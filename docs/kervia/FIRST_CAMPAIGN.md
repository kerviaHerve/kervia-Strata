# First dual NVIDIA measurement campaign

Parent: `ad52647`. Date: 2026-10-07. This record is prepared before running the GPU experiments; the results section will be updated with actual evidence.

## Scope and provenance

Evaluate upstream's existing stage trimming, explicit placement and pipelined windows on the reference two RTX 5070 Ti cards. Use the exact existing upstream engine binary and unchanged model/draft files for both sides. The server source is unchanged. These are **configuration experiments**, not a claim that a new fork CUDA kernel is faster. Any retained fork profile will identify that distinction.

The prepared production configuration remains unchanged. Experimental copies use a separate loopback port, zero prefix checkpoints and a private output directory. The local LLM API is paused only after an idle check, with restoration in the campaign supervisor's `finally` block. Other GPU services must be inactive. No model download, driver change, global tuning, public listener or remote publication is involved.

## Measurement changes

- `tools/kervia_bench.py`: three repetitions of each existing English prompt by default, per-prompt statistics, repetition indices, output counts and an explicit sequential replay policy. The workload text and sampling stay at `kervia-english-code-v1`; the result schema is version 2. The aggregate historical field remains for compatibility, but paired decisions use each prompt separately. Prefix reuse invalidates an uncached summary.
- `tools/kervia_metrics.py`: numeric-only extraction of startup and request evidence. Expert fractions use **all routed entries**, including PCIe work. Requested settings are compared with observed startup state. Raw logs stay private. No detailed GPU profiler is enabled because it changes the normal shared-expert schedule.
- `tools/kervia_validate.py`: public synthetic code, native image, normal/streamed two-tool loops and near-32K/120K retrieval followed by sustained generation. Generated Python runs through an AST gate and a networkless Bubblewrap sandbox with CPU/address-space limits. Optional dependencies come from the existing Strata environment. No private prompt is used.

## Predeclared protocol

One warmup, then three complete replays of the same three-topic sequence, 768 output-token cap, unchanged sampling and French draft vocabulary. Expert adaptation remains enabled, so requests are compared by replay index and independent sessions restart the engine from the same shipped expert profile. Prefix checkpoints are disabled. Actual output lengths and early EOS remain visible; equal token caps do not guarantee equal generated lengths.

First run two independent automatic-placement sessions (A/A). Next compare explicit K=21 without and with trimming, then K=19/23/25 with the same trim policy if earlier gates pass. Pipeline off/2 is a separate step on a measured placement. Maximum initial search: 12 distinct engine configurations; extensions require a documented reason. Same shared binary/model/quantization/context for every run; changing GPU placement is never mixed into the trim-only comparison.

Capture client TTFT/decode/total time, output and input token counts, engine prefill/decode/draft counts, expert-routing denominators and observed cache slots. Sample both GPUs' memory/utilization/power/temperature, process RSS, available host RAM, and cgroup memory/OOM counters. Peak measurements are **sampled**, not allocation-exact. Startup, warmup, decode, validation and long-context phases are labelled separately.

All screened configurations receive functional checks and uncached long prompts when they load successfully. Repeated baseline/finalist sessions establish confirmation; a single screening session cannot establish a repeatable winner. No useful p95 is claimed from three repetitions. Failed configurations and retries remain recorded. A final comparison must retain 131,072 total context, native vision, tool calls and memory headroom; no alternative is promoted when correctness or uncertainty prevents a decision.

## Reproduction

Run the CPU checks in `CONTRIBUTING.md`, including the new helper tests. On a separately started idle experiment server:

```bash
python3 tools/kervia_bench.py --base-url http://127.0.0.1:18080/v1 \
  --model kervia-strata --repetitions 3 --tokens 768 --output benchmark.local.json
```

The functional helpers can be imported from `tools.kervia_validate`; `functional(base, model)` returns each gate independently, and `long_gate(base, model, tokenizer_dir, target)` reports actual token usage, retrieval, output length and prefix reuse. `target` is a raw-text tokenizer budget; API prompt usage includes the template and is recorded separately.

The local supervisor records exact commands, protected config hashes, binary hashes, source revisions, environment and each sample in a private run directory. Publish only reviewed summaries and the public workload source. API keys, model paths and raw host logs do not belong in Git.

## Results and decision

Pending the measured runs. No performance gain or default-profile change is established by this preparation commit.

## Validation and rollback

The pre-change 16 fork and 31 upstream CPU tests passed. New parser and validation checks cover counter denominators, privacy, repeated-input grouping, prefix-cache rejection and isolated generated-code execution. Record their actual final totals with the results. GPU checks are separate.

Preparation correction: the first real long-fixture preflight exposed a missing optional `tokenizers` package. The fixture generator was changed to the exact tokenizer implementation used by Strata's server (`tools.strata_tokenizer`), avoiding a new installation and tokenizer differences. The failed preflight happened before any GPU experiment. A known-correct generated-code fixture was also executed successfully in the sandbox.

Rollback: revert this campaign's helper/documentation commit on the development branch. Stop only the dedicated experiment service and restore the previously active local LLM service. The original model configuration and engine remain untouched; exact hashes are checked after the campaign.
