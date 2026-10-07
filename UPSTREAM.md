# Upstream provenance and maintenance

- Original project: [Niko1221/Strata](https://github.com/Niko1221/Strata).
- Fork: [kerviaHerve/kervia-Strata](https://github.com/kerviaHerve/kervia-Strata).
- Initial upstream revision: `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253` (`v0.1.40.1`).
- Fork established: 2026-10-07, with GitHub's fork relationship and full Git history.
- Initial fork changes: English project documentation, a two-NVIDIA profile generator, a synthetic benchmark client, tests and repository configuration. Engine and server were unchanged at bootstrap.

## Engine experiment imports

The [engine campaign](docs/kervia/ENGINE_CAMPAIGN.md) builds on that initial engine
with these attributed, `cherry-pick -x` imports. These are selected PR heads, not
an assertion that upstream merged or endorsed them:

| Upstream source | Imported commit | Purpose |
|---|---|---|
| [PR1107](https://github.com/Niko1221/Strata/pull/1107) | `8e216160d79ea290464310563197b0571244e5bc` | Group expert gathers for short prefills |
| [PR1316](https://github.com/Niko1221/Strata/pull/1316) | `8e0a7b36ec2a427f879b218b354cde2fdf4487a2` | Retry stale lookup-window costs |
| [PR1163](https://github.com/Niko1221/Strata/pull/1163) | `ed63fa81c2d5919d8a4c4629e1345feabe295463` | Bound spare capacity in growing conversation buffers |
| [PR1164](https://github.com/Niko1221/Strata/pull/1164) | `2a30c0456979c246aee9f8f7c5786dc6b524ddc2` | Borrow checkpoints while keeping the parked conversation |

The fork adds opt-in experiment gates, a measured-cost pipeline launch heuristic,
all-stage prefix validation/restoration for layer splits, CPU/GPU checks and
replay/reporting tools. Original authors and coauthor trailers remain in history.
The Python server and distributed production binaries are not replaced by this PR.

## Attribution and distribution

Keep `LICENSE`, author credit, commit history and third-party license notices intact. `README.upstream.md` preserves the English README at the initial upstream revision; the other upstream language files remain available. The [Strata paper](docs/paper/Strata-Paper.pdf) describes the original work.

The MIT license covers the code as stated in `LICENSE`. It does not replace licenses for model weights, datasets, `third_party/` or other bundled components. Do not include downloaded models, local configurations, credentials or private benchmark traces in releases. The inherited `.github/FUNDING.yml` points to upstream's funding account.

There is no affiliation or endorsement implied by this fork. Upstream multi-GPU capabilities must be credited to upstream. Performance claims must distinguish upstream measurements from changes made here.

## Keeping the fork current

Keep `origin` pointed at this fork and `upstream` at the original repository. Work through a pull request so conflicts and regressions can be reviewed:

```bash
git fetch origin
git fetch upstream --tags
git switch -c maintenance/upstream-sync origin/main
git merge upstream/main
# Resolve conflicts, preserve fork attribution, and run CONTRIBUTING.md checks.
git push -u origin maintenance/upstream-sync
```

Open a PR against this fork's `main`. Record the imported upstream SHA and rerun the relevant hardware checks if the engine changes. Avoid rebasing or force-pushing shared history. CPU CI alone cannot validate GPU performance.

Use fork-prefixed version names such as `kervia-v0.1.0` for future fork releases. Preserve upstream tags and version information; never relabel an upstream binary as a fork build. Build from this checkout when testing a fork engine patch. Upstream's installer and update scripts retain their existing download sources; they are not a fork release channel.

Generic fixes should be proposed upstream when appropriate, with their original authorship and a link to the fork PR. Fork-specific experiments belong here until their evidence and compatibility justify wider use.
