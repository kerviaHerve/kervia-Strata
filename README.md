# kervia-Strata

[![CPU checks](https://github.com/kerviaHerve/kervia-Strata/actions/workflows/ci.yml/badge.svg)](https://github.com/kerviaHerve/kervia-Strata/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A community fork of **[Niko1221/Strata](https://github.com/Niko1221/Strata)** focused on measurable inference improvements for **two NVIDIA GPUs**. The reference platform is **two RTX 5070 Ti cards, with 16 GB of VRAM each**.

Strata's engine, multi-GPU support, OpenAI-compatible server, vision and tool calling come from upstream. This fork preserves the original history, MIT license and attribution. See [upstream provenance](UPSTREAM.md) and the [original README](README.upstream.md).

## Status and scope

The fork adds two-GPU profiles, repeatable synthetic benchmarks, functional checks and documented measurements. The [first campaign](docs/kervia/FIRST_CAMPAIGN.md) identifies a faster opt-in configuration on the reference machine using **existing upstream options and the same upstream binary**. A separate [engine campaign](docs/kervia/ENGINE_CAMPAIGN.md) tests four independently selectable engine changes, including shared-prefix borrowing across split GPUs. These require a fork-built engine and remain off by default.

Our priorities are low latency for coding agents, efficient use of both cards, stable **131,072-token context**, native image input and reliable tool calls. Linux with two NVIDIA cards is the initial validation target. Existing upstream platforms remain in the source tree; they are not all validated by this fork's CI.

## Reference platform

| Component | Reference |
| --- | --- |
| GPUs | 2 × NVIDIA RTX 5070 Ti, 16 GB VRAM per card (32 GB aggregate) |
| Interconnect | PCIe 5.0 x8 and x4; no NVLink |
| CPU / system RAM | Ryzen 9 7900 / 64 GB RAM, separate from GPU memory |
| Model | Qwen3.8-Flash-Next, GSQ-RCO IQ3_XXS, complete expert set |
| Context / KV | 131,072 tokens / INT8, 32,768 resident tokens |
| Execution | Automatic layer split, one active request, speculative decoding |

The model also uses substantial **system RAM**. The historical reference run used about **46.3 GiB of process RSS**, in addition to VRAM. Two 16 GB cards do not make this a 32 GB system-RAM configuration. See [hardware and setup](docs/kervia/DUAL_NVIDIA.md).

## Get started

Use a separate checkout and a free port when another model server is running. Building and loading a model consume significant CPU, RAM and GPU resources.

```bash
git clone https://github.com/kerviaHerve/kervia-Strata.git
cd kervia-Strata
git remote add upstream https://github.com/Niko1221/Strata.git
./setup.sh --check
```

Then follow the [two-NVIDIA setup guide](docs/kervia/DUAL_NVIDIA.md). The guide uses `--build` so the engine comes from this checkout. No fork-specific binary release is published yet; upstream's default prebuilt downloads are still upstream artifacts.

For an installation already prepared by setup, inspect the proposed profile without writing anything:

```bash
python3 tools/kervia_profile.py --config strata-iq3_xxs.json
```

Create a **new** local configuration and start it when the GPUs are available:

```bash
python3 tools/kervia_profile.py --config strata-iq3_xxs.json \
  --output strata-dual-nvidia.local.json
.venv/bin/python serve/server.py --engine strata \
  --config strata-dual-nvidia.local.json --host 127.0.0.1 --port 8080
```

The API base URL is `http://127.0.0.1:8080/v1`, and the profile's model name is `kervia-strata`. The context limit includes input and generated output. Configure authentication before permitting remote access; see [Security](SECURITY.md).

For the measured x8-first/x4-second reference topology, the optional profile uses a 25/23 layer split, stage-weight trimming and two pipeline windows:

```bash
python3 tools/kervia_profile.py --config strata-iq3_xxs.json \
  --profile configs/dual-nvidia-5070ti-128k-measured.json \
  --gpus 0,1 --draft-vocab fr --output strata-measured.local.json
```

This creates a separate config; it does not switch a running service. Read the [conditions, results and rollback](docs/kervia/FIRST_CAMPAIGN.md) before selecting it. Automatic placement remains the generator's default. Re-measure for a different GPU order, available VRAM or workload.

## Measurements

The first campaign's final paired confirmation measured **22–26% higher per-prompt median decode rates** on three coding prompts and **14–27%** on three additional English/French prompts. Uncached first-token latency at 119,979 input tokens changed from **30.81 s to 24.48 s**. Each prompt had three 768-token outputs. These results compare configurations on one shared workstation; a resident embedding service occupied about 2 GB on GPU 0, and complete activity isolation was not established. See [all trials and limitations](docs/kervia/FIRST_CAMPAIGN.md). They must not be compared directly with the different historical workload below.

The subsequent [engine campaign](docs/kervia/ENGINE_CAMPAIGN.md) measured an
**80.7% reduction in first-token latency** when returning to a sibling conversation:
**1.954 s → 0.378 s**, with 4,682 instead of 3,056 cached input tokens. This repeated
synthetic result uses split-GPU prefix borrowing and the same 2 GiB parked-cache
budget on both sides. It is not a general decode-rate gain or a direct Hermes/Privy
client benchmark. The other three engine experiments remain unpromoted; all four
flags are off by default. The record includes build identities, failures, memory
costs, functional checks and rollback.

Historical measurements on the reference machine, **before any fork changes**, used three 768-token outputs and uncached synthetic French prompts:

| Backend | Median decode, tokens/s | First token, 32,030 input tokens | First token, 120,029 input tokens |
| --- | ---: | ---: | ---: |
| Upstream Strata, Flash Next IQ3_XXS | 130.92 | 9.18 s | 30.49 s |
| llama.cpp, Flash Next IQ3_XXS | 29.58 | 58.05 s | 234.14 s |
| llama.cpp, Qwen3.8 27B Turbo | 115.33 | 22.92 s | 105.57 s |

These are observations on one machine, not quality scores, single-GPU scaling results or promised performance. The Turbo row uses a different model. The [measurement record](bench/results/kervia/2026-10-07-reference.json) and [method and limitations](docs/kervia/BENCHMARKING.md) explain the workload, cache policy and memory costs. The new English benchmark is a different workload and must establish its own baseline.

## Development

- [Roadmap and acceptance criteria](docs/kervia/ROADMAP.md)
- [Contributing and CPU checks](CONTRIBUTING.md)
- [Benchmark methodology](docs/kervia/BENCHMARKING.md)
- [Upstream multi-GPU architecture](docs/MULTI_GPU.md)
- [Original installation and API documentation](README.upstream.md)
- [Security reporting](SECURITY.md) · [Code of conduct](CODE_OF_CONDUCT.md)

New fork documentation, issues and pull requests use English. Upstream translations are retained with their original content.

## License and credit

[MIT](LICENSE). Copyright and original authorship remain credited to Niko1221 and the Strata contributors. Third-party components retain their own notices. Model weights are downloaded separately and have their own licenses. The inherited GitHub Sponsor link supports **upstream Strata**, not this fork's maintainer.
