# Neem

A physics-grade heat twin for Delhi schoolyards, built for the WeMakeDevs x AWS Environmental Hacks (Heat & Water track, deadline Sun 11 Oct 2026, 8 PM IST). SOLWEIG computes how hot every square metre of a school feels; a child body twin turns that into core temperature and water loss; planners drag trees and see the result instantly, verified by physics. "Good" means every number on screen traces back to a model run we can reproduce.

## Commands
- `just check`: format check, lint, types and fast tests (must pass before any commit)
- `just test-all`: includes the slow SOLWEIG engine tests
- `just fmt`: fix formatting and autofixable lint
- `just ingest`, `just scene <id>`, `just rank`: data pipeline
- `just up` / `just down`: local stack (emulated AWS, API, worker)

## Layout
- `packages/neem-core`: physics. Scenes, interventions, SOLWEIG engine, fast surrogate, child twin, optimiser
- `packages/neem-data`: open-data ingest (Overture, Meta canopy, Copernicus DEM, OSM, weather), scene builder, city batch
- `packages/neem-api`: FastAPI service
- `packages/neem-worker`: queue consumer for verification and optimisation jobs
- `web/`: Astro + React islands, light editorial site
- `recon/`: GPU container that turns phone video into a 3D model and a DSM
- `infra/`: docker compose (local) and SAM template (AWS)
- `docs/`: architecture and ADRs

## Conventions
- uv is not on this shell's PATH: prefix `$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"`.
- Grids are north-up, 1 m, EPSG:32643 (UTM 43N). DSM is absolute metres; CDSM is height above ground.
- Physics code may use conventional symbols (Ta, Tmrt, H); everything else follows ruff naming.
- Never claim a temperature without the run that produced it. Tests marked `slow` run SOLWEIG.
- Commit history must stay inside the event window (from 8 Oct 2026). No AI attribution anywhere.
- The repo is GPL-3.0 because SOLWEIG is.
