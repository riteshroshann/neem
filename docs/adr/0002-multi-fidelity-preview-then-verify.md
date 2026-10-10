# 2. Multi-fidelity: instant preview, physics verification

Date: 2026-10-10
Status: accepted

## Context

Drag-a-tree must respond within one frame budget (under 100 ms). SOLWEIG takes seconds. The optimiser needs thousands of evaluations per school.

## Decision

Two tiers that share inputs. T0 recomputes the shadow mask for the edited surface (ray marching on the DSM toward the sun) and maps it to Tmrt with a per-hour regression calibrated against a T1 SOLWEIG run of the same school: `Tmrt ≈ a_h + b_h · sunlit + c_h · svf`, then UTCI from a per-hour lookup table. T1 is a full SOLWEIG run. The UI shows T0 immediately and replaces it with T1 when the job finishes. The optimiser searches with T0 and verifies its Pareto front with T1.

## Consequences

- T0 has two implementations (Python and TypeScript). A differential test pins them to each other on shared fixtures.
- T0 error against T1 is measured per school and shown in the UI as a confidence band. If calibration error exceeds 2.5 °C MAE, the preview is disabled for that school.
- Changes to SVF from new trees are approximated in T0 (local SVF reduction); T1 captures them exactly.
