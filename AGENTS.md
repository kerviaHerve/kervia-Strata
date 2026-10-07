# AGENTS.md

Strata runs the Qwen3.8-Flash-Next mixture-of-experts model (and its Coder, Swift 1.5 and Unsloth variants) on a
normal PC: one NVIDIA or AMD graphics card plus system RAM, on Windows or Linux. It has a C++/CUDA/HIP engine
(`src/`, `include/`), a Python server with an OpenAI- and Anthropic-compatible API and a web app (`serve/`), and a
one-click installer (`setup.py`, started by `START-HERE.bat` / `setup.sh`).

## Installing Strata for a user

Follow **[docs/AI_SETUP.md](docs/AI_SETUP.md)**: check the PC, pick the model by RAM, run setup non-interactively,
start and verify the server, and connect the user's apps. Never expose the server beyond `127.0.0.1` without
`--api-key`. As an alternative to shell commands, Strata's MCP server ([docs/MCP_SERVER.md](docs/MCP_SERVER.md))
offers the same steps as tools.

## Working on the code

- How the engine works, every measured number, the API and all settings: [docs/DETAILS.md](docs/DETAILS.md) and
  the [paper](docs/paper/Strata-Paper.pdf).
- AMD (HIP) build and validation: [docs/AMD_HIP.md](docs/AMD_HIP.md); multi-GPU: [docs/MULTI_GPU.md](docs/MULTI_GPU.md).
- Setup's own tests run without a GPU or downloads: `python tools/test_setup_<name>.py` (for example
  `tools/test_setup_amd.py`, `tools/test_setup_choices.py`).
- Keep the docs' style: plain words, measured numbers with what they were measured on, no claims without a
  measurement.

## kervia-Strata fork conventions

- Read `UPSTREAM.md`, `CONTRIBUTING.md` and `docs/kervia/ROADMAP.md` before fork-specific changes.
- Write new fork documentation, issues and PRs in English. Preserve upstream credit, licenses and history.
- The initial reference platform is two RTX 5070 Ti 16 GB cards, with separate system RAM. Do not conflate VRAM with system RAM.
- Keep production installations separate from this development checkout. A repository task does not authorize restarting a model service, replacing its config, downloading weights or occupying its GPUs.
- Start with the CPU checks in `CONTRIBUTING.md`. They do not validate CUDA builds, GPU execution or performance.
- Benchmark claims require identical public synthetic workloads and exact baseline/candidate revisions. Label the historical upstream baseline honestly; do not attribute it to fork optimizations.
- Document every change using the required change record in `CONTRIBUTING.md`: evidence, exact change, reproduction, measured results or explicit untested status, decision and rollback. Never substitute an assumed gain for a target-hardware measurement.
- Keep generated configs, credentials, private logs, prompts and model weights out of Git. Review sanitized summaries before publishing.
