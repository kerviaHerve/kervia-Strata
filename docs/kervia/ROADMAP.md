# Dual NVIDIA roadmap

The reference workload is a single coding agent with native vision, tool calls and at least 131,072 tokens of total context on two RTX 5070 Ti 16 GB cards. Broader two-NVIDIA configurations are welcome when accompanied by measurements.

## 1. Establish comparable measurements

The repository includes repeated public decode workloads, synthetic long-context/image/tool checks and CPU regression checks. The [first campaign](FIRST_CAMPAIGN.md) compares existing upstream configuration options using the same engine binary. The [engine campaign](ENGINE_CAMPAIGN.md) separately compares fresh reference/fork builds and disabled/enabled options in the same fork binary. Keep model quality and memory costs visible alongside speed.

Acceptance: exact revisions and commands, three or more decode runs, uncached 32K and near-128K probes, per-card VRAM and process RAM, plus functional results. No fork speedup is claimed until this comparison exists.

## 2. Measure placement and transfer costs

Compare automatic placement with explicit layer boundaries on asymmetric PCIe links. Measure both GPU orders, per-stage time, host-to-device traffic and remote expert behavior. Identify the bottleneck before changing kernels or scheduling.

First-campaign progress: automatic K=21 and explicit K=19/21/23/25/27/29 were measured in one GPU order, with stage trimming and two-window pipelining. A serial control matched the pipeline's observed expert-cache capacities. The other GPU order, full transfer traces and remote helpers remain untested.

Acceptance: repeatable latency or throughput improvement across short and long prompts, without losing native vision, tool calls, context capacity or memory headroom. Keep a fallback to upstream automatic placement.

## 3. Improve expert and KV allocation

Investigate per-device cache allocation, prefill memory peaks, draft placement and KV residency under the measured topology. Evaluate longer conversations and context growth rather than a short-chat-only optimum. Experimental controls must remain opt-in until validated.

The engine campaign implements split-device prefix borrowing with donor pinning,
validation of every stage before writes, and bounded parked RAM. Its sequential
sibling workload is an interleaving check; concurrent serving remains a separate
roadmap item.

Acceptance: no OOM in the published reference workloads, no hidden system-RAM or swap dependency, and no silent change to model behavior or quantization. Publish regressions and tradeoffs.

## 4. Evaluate concurrent workloads

After the one-agent path is stable, test multiple requests and distinguish aggregate throughput from individual latency. Compare upstream batching and pipeline options before introducing a fork-specific scheduler.

Acceptance: request isolation, cancellation, streaming and tool-call correctness; latency distributions and memory use at each concurrency level.

## 5. Maintain and contribute upstream

Import upstream fixes through reviewed synchronization PRs. Keep engine patches small enough to audit and propose generally useful fixes upstream with attribution. Add a fork release only after a reproducible build and hardware regression pass. Do not present an upstream downloaded binary as a fork-optimized build.

This roadmap is a development plan, not a list of completed optimizations or release dates.
