# Contributing to kervia-Strata

This is a community fork of [Niko1221/Strata](https://github.com/Niko1221/Strata). Our focus is measurable improvements for two NVIDIA GPUs. Please read [upstream provenance](UPSTREAM.md), the [roadmap](docs/kervia/ROADMAP.md) and the [code of conduct](CODE_OF_CONDUCT.md).

Use English for new issues, pull requests, code comments and fork documentation. Preserve existing attribution and licenses. Changes are contributed under the repository's MIT license; third-party components keep their own terms.

## Workflow

Create a focused branch from this fork's `main` and open a pull request here. Describe the problem, the resulting behavior and how it was checked. Preserve unrelated user changes and upstream compatibility. `main` requires a PR and successful CPU checks; do not force-push shared history.

Keep kernel, scheduling, configuration and documentation changes reviewable. Prefer existing dependencies. A generic upstream bug can also be reported or fixed upstream, but do not open duplicate reports without linking the related work.

## CPU checks

These checks require Python 3.11 or 3.12 and the standard library. They do not download models or use GPUs:

```bash
python3 -m unittest discover -s tests/kervia -p 'test_*.py' -v
python3 -m unittest tools.test_setup_config tools.test_setup_configs \
  tools.test_setup_parallel tools.test_setup_remote_opt tools.test_setup_golden
python3 -m py_compile tools/kervia_profile.py tools/kervia_bench.py
```

Run additional relevant upstream tests when changing their code. CI is deliberately a CPU check, not a CUDA build or performance certification. Do not run untrusted pull requests on a production machine or expose credentials to a self-hosted GPU runner.

## Performance changes

Follow [BENCHMARKING.md](docs/kervia/BENCHMARKING.md). Include hardware, both build SHAs, model revision, exact settings, all measured runs, cache policy, memory usage and functional regressions. Keep baseline and candidate workload identical. Avoid claims based on a cached prompt compared with an uncached one.

New experiments should be opt-in until verified. Preserve the OpenAI-compatible API, streaming, native vision, tools and the reference context capacity. Document rollback to the previous profile or engine.

## Private data and security

Do not commit local run configurations, credentials, `.env` files, model weights, private prompts or raw host logs. Publish only reviewed synthetic fixtures and sanitized measurements. Use [private vulnerability reporting](https://github.com/kerviaHerve/kervia-Strata/security/advisories/new) for security bugs; see [SECURITY.md](SECURITY.md).
