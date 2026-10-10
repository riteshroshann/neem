# 1. SOLWEIG as the physics engine

Date: 2026-10-10
Status: accepted

## Context

We need the radiant heat a person feels (mean radiant temperature, Tmrt) and a thermal comfort index (UTCI) at 1 m resolution, driven only by a surface model and weather. Options: ENVI-met (closed, slow, hours per run), a hand-written shadow model (fast, physically incomplete), SOLWEIG (open, peer-reviewed, full shortwave and longwave budget, the model behind UMEP).

## Decision

Use SOLWEIG through UMEP's Rust implementation (`solweig` on PyPI), which runs on GPU via WebGPU and falls back to CPU. Keep it behind a `HeatEngine` protocol so the engine can be swapped (for example SOLWEIG-GPU v2 for WBGT).

## Consequences

- A 200 x 200 m yard at 1 m runs in about 4 s on the laptop GPU, which is fast enough for verification, not for dragging. That forces the fast tier in ADR 0002.
- The package is beta (0.1.0b96). We pin it and guard it with golden tests.
- SOLWEIG is GPL-3.0, so this repository is GPL-3.0.
