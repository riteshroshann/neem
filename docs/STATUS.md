# Neem: status and handoff

Last updated: Sat 10 Oct 2026, about 1:05 PM IST. Deadline: **Sun 11 Oct 2026, 8:00 PM IST** (WeMakeDevs x AWS Environmental Hacks, Heat & Water track). Submission = public repo + 3-minute YouTube video (AWS visible on screen) + short writeup listing AI tools used.

## The idea in one line

A physics-grade heat twin for every Delhi schoolyard: SOLWEIG computes how hot each square metre feels to a child, a child body twin turns it into core-temperature rise and water lost, and a planner drags trees onto the yard and sees the effect instantly (preview), then verified by full physics.

## Done (all committed and pushed to github.com/riteshroshann/neem, private)

- Monorepo: uv workspace (`neem-core`, `neem-data`, `neem-api`, `neem-worker`), justfile, ruff + basedpyright + pytest, GPL-3.0, ADRs 0001 to 0007, `docs/architecture.md`.
- `neem-core`: grid, scene, interventions (trees, shade sails, costs), NOAA sun position, numba shadow caster, SOLWEIG engine adapter (GPU via WebGPU), anchored T0 preview tier (`surrogate.py`), JOS-3 child twin reporting rise above rest, school-day schedules (morning + afternoon shift), exposure metrics, heat palette.
- Tests: 27 fast + 4 slow, all green. Includes property tests (shadow monotonicity), differential tests (our shadows vs SOLWEIG > 97% agreement; T0 vs T1 on unseen designs), a regression test for SOLWEIG mutating inputs, and job-port contract tests against moto (file and DynamoDB stores, SQS).
- `neem-data`: OSM schools (Overpass), Overture buildings via STAC-selected files (3 of 512), Meta canopy height v2 and Copernicus DEM read as remote COGs, ERA5 forcing via Open-Meteo, scene builder, twin runner, city batch (`rank_one` + local process pool), design verification job, publish step.
- `neem-api`: FastAPI (`/schools`, `/schools/{id}`, `/layers.bin`, `/calibration`, `/child`, `POST /designs`, `/jobs/{id}`), job ports with local (files + threads) and AWS (DynamoDB + SQS) adapters. Smoke-tested: ranking, twin summary, 2.8 MB binary layers, a design job verified in about 10 s.
- `neem-worker`: SQS long-poll loop + Lambda handler (same `run_job`), bootstrap for table and queue.
- `infra/Dockerfile` (one image for API and worker, Lambda Web Adapter included) and `infra/compose.yaml` (moto + bootstrap + api + 2 workers). Image build was started but not confirmed.

## Results so far (real runs, reproducible)

- Showcase day: **Mon 27 April 2026**, Delhi max 42.2 C (hottest school day before the 11 May summer vacation; 29 June was in the vacation, do not use it).
- OSM: 1,100 Delhi schools, 823 with grounds, 242 government.
- Overture: 1,895,637 Delhi buildings; only about 0.5% have height or floor count (heights mostly from a footprint prior). This is the story for the 3D phone-video moonshot.
- City ranking (2 m, 9/11/13 h): 792 run, **766 ok**, 26 have no open ground. 77 schools/min, median 2.7 s each. Mean yard UTCI 39.0 to 44.7 C (median 42.0). **Tree canopy vs heat r = -0.95** across schools. 34% of schools spend over a quarter of yard-hours in extreme heat stress.
- Full 1 m twins built for: `osm-w1321574340` Kendriya Vidyalaya Sector 25 Rohini (2.9 km from DTU, 35th hottest), `osm-w1096874054` School of Specialised Excellence (4.6 km, 40th), `osm-w1158946096` MCD Primary School (5.0 km), `osm-w78786253` Rani Chenamma Sarvodaya Kanya Vidyalaya (6.0 km, mid-table, nice courtyard). Each twin takes about 30 s.
- Rani Chenamma, 8 to 13 h: yard mean UTCI 40.9 C, 70% of yard-hours very strong stress, 21% extreme. Child twin (morning shift): core rise 0.96 C, 868 ml water lost.
- SOLWEIG on the laptop GPU: about 3.5 s SVF + 0.3 s per hour for a 250 x 280 grid.

## Known issues to fix

- T0 preview error on cells a design changes is 4 to 5.6 C at midday on real schools (exact elsewhere). Options: more probe designs in calibration, add features (crown-edge, SVF change under new canopy), or show the band honestly and rely on the 6 s physics verification. The UI must show the band.
- Canopy warp of uint8 tiles logs "value 0 changed to 1" (GDAL nodata clash). Harmless because canopy under 2 m is zeroed; clean up by warping with nodata 255.
- Overture heights are mostly priors. Possible improvement: GHSL built-up height (100 m) as a better prior.
- `publish.py`, `palette.py` and the `publish` CLI command are written but **not yet run or tested**.

## Pending, in order

1. **Run `just` publish**: `uv run neem-data publish` (writes `web/src/data/*.json`, `web/public/thumbs/*.png`).
2. **Web** (`web/`, Astro + React island, Bun, Biome, TypeScript strict), direction already decided via atelier:
   - Look: white paper, black ink, no UI accent; the only colour is the heat ramp (`neem_core/palette.py`). Type: Instrument Serif (display, big numbers) + Geist (UI, tabular figures). Square corners, 1 px rules, no cards, no chips.
   - `/` index: huge serif headline, three real numbers (766 schools, r = -0.95, 1 in 3), dot map of all schools with no basemap (SVG), ranked table with heat thumbnails, links to the four twins.
   - `/school/[id]`: React planner island. Canvas heat map at 1 m, hour scrubber 7 to 13, tools: plant tree (species), shade sail, undo, clear. Port T0 to TypeScript (shadow caster in `shadow.py`, features + delta model in `surrogate.py`, LUT). Readouts: yard UTCI, cost in rupees, "Verify with physics" (POST design, poll job), before/after, child chart (SVG: core rise over the day with activity bands, water lost).
   - `/method`: data sources, physics, fidelity tiers, child-twin caveat, validation tests, limitations, AWS architecture diagram, credits and licenses. Footer: "Engineered by Ritesh Roshan".
   - Note: `bun` is installed but not on this shell's PATH: `C:\Users\roshh\AppData\Local\Microsoft\WinGet\Packages\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64`. Run `bun x create-astro` from inside the repo (it failed from /tmp).
   - Verify with webapp-testing screenshots at 390 / 1280 / 1920 and the essentials skill before calling it done.
3. **3D moonshot** (`recon/`, ADR 0007): needs the user's 60 to 90 s phone video of an empty courtyard (no children on camera, principal's permission). Nerfstudio container on the RTX 4050 (6 GB): COLMAP poses, splatfacto splat, dense points to DSM/CDSM, georeference to the Overture footprint. Web viewer for the splat.
4. **AWS** (user has no account yet): create account, $200 credits, MFA, billing alarm, Builder Center student verification, Bedrock not required. Then `infra/template.yaml` (SAM): S3 lake bucket, DynamoDB jobs table, SQS + DLQ, API Lambda (container, Lambda Web Adapter), worker Lambda (SQS trigger), Step Functions Distributed Map for `rank_one`, CloudFront + S3 for the web, CloudWatch. Add an S3-backed lake read path (download scene/run files to /tmp on demand). Show the console in the video.
5. **Optional**: a lean optimiser (pymoo NSGA-II on T0, verify the Pareto front with T1) for "AI redesign"; Strands agent is not required.
6. **Submission**: make the repo public, README polish (vibe skill), 3-minute video script (20 s problem, 90 s product, 40 s AWS console, 30 s impact), writeup listing AI tools used, Builder Center blog for the AirPods prize. Commit history must stay inside the event window.

## How to resume

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"   # uv, just, ruff, gitleaks
$env:PYTHONUTF8 = "1"
uv sync
just check                          # fast suite
uv run neem-data ingest all         # schools + Overture buildings (about 3 min)
uv run neem-data weather --start 2026-04-27 --end 2026-04-27
uv run neem-data twin osm-w1321574340   # repeat for the other three ids
uv run neem-data rank --workers 4   # about 10 min, resumable
uv run neem-data publish
uv run neem-api                     # http://127.0.0.1:8000/docs
```

`data/` (the lake) is gitignored: everything above regenerates it from public sources.
