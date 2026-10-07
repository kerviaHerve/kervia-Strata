# Benchmarking and evidence

The objective is lower latency and better use of two NVIDIA GPUs while retaining correctness, image input, tool calling and a usable 128K context. A tokens-per-second figure alone does not establish any of those properties.

## Historical baseline

[2026-10-07-reference.json](../../bench/results/kervia/2026-10-07-reference.json) contains a sanitized summary of local measurements made **before this fork's changes**, on upstream revision `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`. No hostname, network address, credentials, user prompts or private logs are published.

Hardware: two RTX 5070 Ti 16 GB, PCIe 5.0 x8/x4, Ryzen 9 7900, 64 GB system RAM. Strata used the complete GSQ-RCO IQ3_XXS expert set, automatic placement (21/27 layers observed), one active request, MTP draft length 4, INT8 KV and a 32,768-token resident KV window. The French draft vocabulary was selected. Model-changing control vectors were disabled.

The legacy workload (`legacy-fr-code`) used three synthetic French coding prompts, each producing 768 tokens after warmup, with temperature 0.6, top-p 0.95, top-k 20, min-p 0 and seed 42. Thinking was disabled. Rates are client-observed stream decode rates. The Flash Next llama.cpp comparison used a 512-token microbatch and no MTP; the Turbo comparison used another model with MTP. This is a comparison of deployed configurations, not an isolated engine or model-quality experiment.

Long-prompt probes used 32,030 and 120,029 actual input tokens, zero cached tokens and three synthetic retrieval markers. They demonstrate those probes, not general long-context reasoning quality. Basic generated-code cases, synthetic image OCR/shapes, two tool calls and streaming succeeded in the original evaluation. These functional probes and their legacy harness are not part of the new CPU CI.

The detailed legacy harness and raw host logs remain private. The published JSON is a derived measurement record, not a fully reproducible raw experiment. Future claims must use published synthetic workloads and record exact build/model revisions.

## Run the English decode benchmark

Prepare a **benchmark** config using `tools/kervia_profile.py --benchmark` and start it on an available port. Make sure no other workload is competing for the GPUs. Use the same model, quantization, draft vocabulary, context, cache settings and sampling parameters for both builds.

```bash
python3 tools/kervia_bench.py --base-url http://127.0.0.1:8080/v1 \
  --model kervia-strata --output benchmark.local.json
```

The standard-library client sends one warmup followed by three complete replays of three fixed synthetic English coding prompts (nine measured requests). `--repetitions` changes the replay count. Schema 2 records each run, per-prompt medians/ranges, token usage, content hashes, first-token latency and total time. Compare matching prompts and replay indices; the aggregate median is descriptive. Positive cached-input counts invalidate the uncached summary. The workload is named `kervia-english-code-v1`; **it is different from the historical French workload**.

The [first campaign](FIRST_CAMPAIGN.md) establishes this new baseline and measures upstream configuration options on the reference machine. Its [sanitized results](../../bench/results/kervia/2026-10-07-first-campaign.json) include every completed trial, a separate confirmation workload, functional checks and sampled resource usage. These are measurements with an unchanged upstream binary; they do not establish a new fork engine's speed.

The rate estimate is `(completion_tokens - 1) / (last_content_time - first_content_time)`. SSE buffering, grouped token delivery and speculative decoding affect this client estimate. Use engine timing as a separately labeled cross-check. Role-only chunks do not count as first content. Missing token usage, truncated streams and intervals too short to measure cause failure. Early EOS is reported and makes unequal output lengths a comparison limitation.

An API key can be provided through `STRATA_API_KEY`; it is never printed or stored in results. The default client accepts loopback URLs only, rejects embedded URL credentials and follows no HTTP redirects. Testing a remote server requires `--allow-remote` and an appropriate protected network path. Result files are created exclusively with mode 0600. Their default names are ignored by Git; review any summary before publishing it.

The request's `cache_prompt: false` is insufficient to disable Strata engine checkpoints: use **`--prompt-cache 0`** in the engine arguments. Compare uncached prefill separately from cached conversation continuation. The historical 120K cached run reused 120,022 tokens and reached first output in about 0.24 seconds; that is not a 120K uncached prefill result.

## Before claiming an optimization

1. Record full upstream/fork commit IDs, build flags, compiler/toolkit/driver versions, model and draft revisions, per-card VRAM, system RAM and PCIe topology. State the selected GPU order and actual split.
2. Keep the machine idle apart from the workload. Separate cold startup, warm decode, uncached prefill and cached continuation. Run the same synthetic workload at least three times per configuration, report every run and the median, then repeat in alternating build order if the difference is small.
3. Report peak VRAM per GPU, process RSS and minimum available system RAM. Keep filesystem cache distinct from process RSS. Check OOM events, CPU use, thermal throttling and swap activity; do not hide a RAM or quality regression behind higher decode speed.
4. Measure both 32K and near-128K input latency and verify known markers. Preserve room for output within the 131,072-token limit. Test image input and realistic multi-step tool calls separately.
5. Test generated code against meaningful behavioral assertions. Do not execute arbitrary model output on a production host; use an isolated test environment. Report failures alongside speed results.
6. Attach sanitized summaries and exact reproduction commands to the PR. Never publish tokens, private prompts, model weights, local config paths or raw system logs.

The decode CLI measures warm text streaming. `tools/kervia_validate.py` provides synthetic code, native-image, tool and long-context gates; `tools/kervia_lifecycle.py` adds prefix restoration and stream cancellation. `tools/kervia_metrics.py` extracts numeric engine evidence. GPU/process telemetry and service supervision for the first campaign were collected separately in a private host harness; they are not part of the decode CLI. CPU CI validates the helper tools and selected upstream setup behavior; it does not compile CUDA or prove a hardware speedup. A single-GPU control has not yet been measured for this reference platform.
