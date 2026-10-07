# Two NVIDIA GPUs: reference setup

This profile targets one active coding-agent request on two RTX 5070 Ti 16 GB cards. It combines existing upstream options; it is not a new parallel execution engine. Read [upstream multi-GPU documentation](../MULTI_GPU.md) for the layer-split architecture and its limitations.

## Memory and topology

- Each reference GPU has 16 GB VRAM. The combined 32 GB is distributed across two devices, not a single contiguous allocation.
- The reference machine has **64 GB system RAM**, about 61 GiB usable. The model needs RAM as well as VRAM: observed engine/server process RSS was about 46.3 GiB during the uncached benchmark and about 47.1 GiB in the cached production configuration.
- The reference PCIe links are Gen 5 x8 and x4, with no NVLink. Equal VRAM does not guarantee equal transfer bandwidth. Check `nvidia-smi topo -m` and `nvidia-smi -q -d PCI,MEMORY` on your own machine.
- Leave headroom for the desktop and other services. A 1,024 MiB reserve per GPU is a starting value, not an OOM guarantee.
- The model's main GGUF download is about 75.84 GB, plus about 0.91 GB for the image projector and additional draft, packed and build assets. Follow setup's free-space check and allow more space for build products and multiple configurations.

Automatic placement produced **21 / 27 layers** on the reference machine. This is an observation, not a fixed split to copy to every system. GPU order, free VRAM and topology can change the appropriate split.

## Prepare a separate installation

Clone the fork as shown in the [README](../../README.md). The installer can install dependencies and download large model files. Do not run it inside a production checkout during an unrelated task.

For a source build, use a CUDA toolkit and host compiler compatible with your distribution and GPU. The reference Ubuntu 26.04 / glibc 2.43 build required CUDA 13.2.86: CUDA 13.0 failed on an `rsqrt` exception-specification conflict. This is a tested combination on that host, not a requirement for all distributions. `CUDA_HOME` or `CUDA_PATH` can select an existing private toolkit; avoid changing the system driver just to select a compiler.

```bash
./setup.sh --check
./setup.sh --yes --no-start --build --backend cuda \
  --model IQ3_XXS --gpus 0,1 --layer-split auto --parallel 1 \
  --context 131072 --kv int8 --kv-streaming on \
  --vision gpu --vision-tokens 1024 --draft-vocab en \
  --vram-reserve-mib 1024 --experimental-speed-projection off --no-browser
```

For existing weights, see setup's `--gguf-dir`, `--models-dir` and `--data-dir` options. Model and draft files must be prepared before applying the profile. This English example chooses the English draft vocabulary; the historical French baseline used `fr`. Keep the vocabulary identical when comparing two builds.

## Apply the profile

`configs/dual-nvidia-5070ti-128k.json` describes profile options. It is **not** a runnable Strata config and contains no machine-specific paths. `tools/kervia_profile.py` merges it into a configuration that setup already generated:

```bash
# Dry run: validate without writing or starting anything.
python3 tools/kervia_profile.py --config strata-iq3_xxs.json

# Service profile: six conversation checkpoints.
python3 tools/kervia_profile.py --config strata-iq3_xxs.json \
  --gpus 0,1 --output strata-dual-nvidia.local.json

# Benchmark profile: no prefix checkpoints.
python3 tools/kervia_profile.py --config strata-iq3_xxs.json \
  --gpus 0,1 --benchmark --output strata-dual-nvidia-bench.local.json
```

The helper preserves model paths, native GGUF options, tokenizer, prepared draft vocabulary, image encoder, library paths and authentication. It selects two distinct CUDA GPU indices, automatic layer placement, one active request, INT8 KV, a 32,768-token resident KV window, a 131,072-token maximum context, speculative decoding with four draft tokens and remote expert optimization.

Output is a new file with owner-only permissions on Linux; an existing output is never overwritten. No server is started, restarted or stopped. Explicit batch/split engine overrides and control vectors are rejected so the reference configuration cannot silently inherit those experiments. `--draft-vocab` only selects assets that setup already prepared; it does not download them.

Start the new configuration with the Python environment that contains Strata's dependencies:

```bash
.venv/bin/python serve/server.py --engine strata \
  --config strata-dual-nvidia.local.json --host 127.0.0.1 --port 8080
```

The server can be reached at `http://127.0.0.1:8080/v1` with model name `kervia-strata`. **131,072 tokens is the combined input/output window.** Leave output space when building a long prompt. Vision tokens also consume context.

## Validate and recover

Check the startup log for both selected GPUs, the actual layer split, model revision, KV configuration and context. Make a real text request, then test native image input and tool calls with synthetic data. Run the [benchmark protocol](BENCHMARKING.md) before making performance claims. A successful profile dry run proves configuration generation only; it does not prove GPU execution or memory fit.

Keep your previous prepared config. To roll back a profile trial, stop that trial server normally and start the previous config using the same service manager you used before. Do not run two copies against the same full GPU allocation. The helper never changes systemd units, network listeners or firewall rules.
