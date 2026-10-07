# Engine campaign: four independent changes

Status: implementation and measurement in progress. No performance claim yet.

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
| 4. Shared prefixes on split GPUs | Upstream PR1164 `2a30c0456979c246aee9f8f7c5786dc6b524ddc2` and dependency PR1163, extended by this fork | Alternating sibling conversations: reused tokens, TTFT, retained cache bytes, prefix integrity, all-stage validation before writes |

Each experiment is opt-in, independently selectable, and compared with the same
disabled path. Budget: four isolated candidates, one combined candidate, and up
to three corrective candidates if a correctness failure is found. At least three
repetitions per synthetic timing workload; repeat reference and retained candidate.
Keep every failure and rejected variant. Long-context, vision, code execution,
streamed tool calls and cancellation qualify a retained combination. No raw user
conversation is used. No benchmark timing runs during compilation.

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
