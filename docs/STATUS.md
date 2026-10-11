# Neem: status and handoff

Last updated: Sun 11 Oct 2026, about 1:30 PM IST. Deadline: **Sun 11 Oct 2026, 8:00 PM IST** (WeMakeDevs x AWS Environmental Hacks, Heat & Water track). Submission = public repo + 3-minute YouTube video (AWS tooling visible on screen) + short writeup listing AI tools used (ready: `docs/SUBMISSION.md`).

Track chosen: **Build It** (AWS open-source tools, on the machine, no AWS account). Tools in use: **Strands Agents SDK, SAM CLI, LocalStack, Cedar**. Ship It (real AWS deploy) is optional later and needs an account; `infra/template.yaml` is ready for it.

## Live

- Site: **https://neem-lemon.vercel.app** (Vercel project `neem`, account riteshroshann). Static Astro + one Vercel Function `web/api/email.ts` (Resend). Every push to `main` deploys to production: the project's Root Directory is `web` (it was the repo root, which is why the push builds failed in 5 s with "no package.json").
- Repo: github.com/riteshroshann/neem (private; make public before submitting).
- Resend sends only to the account address (no verified domain): `RESEND_TO` = riteshroshansahoo01@gmail.com. Key lives in `web/.env.local` (gitignored) and Vercel env. Rotate it after the hackathon: it was pasted in chat.

## Done

- Physics core (`neem-core`): scenes, interventions, sun, numba shadow caster, SOLWEIG engine (GPU), anchored T0 preview, JOS-3 child twin (rise above rest), schedules, exposure, palette.
- Data (`neem-data`): OSM schools, Overture (3 of 512 files via STAC), Meta canopy v2, Copernicus DEM, ERA5 via Open-Meteo, scene builder, twin runner, city batch, design verification, publish (ranking, thumbnails, static twin files, agent plans), S3-backed lake for Lambda (`sync_from_s3`, `upload`), Lambda entry points for the ranking map (`lambda_rank.handler`, `collect`).
- API (`neem-api`): FastAPI, job ports (files+threads / DynamoDB+SQS), **Cedar** authorization (`policies/neem.cedar` + schema): anyone explores; verification has a size and rate budget; only a school's planner approves, only verified plans. Token identity table (`NEEM_DEV_TOKENS`) stands in for Cognito.
- Worker (`neem-worker`): SQS loop + Lambda handler; bootstrap creates table, queue, lake bucket, seeds the lake, queues a demo job.
- Planner agent (`neem-agent`): **Strands Agents** + Ollama `qwen3:4b` on the GPU. Tools: brief, plant_trees (hottest-first placement, budget enforced in the tool), add_shade_sail, preview, verify. Plans saved to `lake/plans/` and published.
- Web (`web/`): one theme, everything drawn in square cells like the 1 m physics grid. Home, `/story` and `/method` sit wholly on the night sky (warm black with a field of star cells; `Base` takes `night="page"`); school pages and the 404 keep night heads over a paper body. The night footer strip is its own drawing (`ground-night.svg`): floodlit Qutub Minar, India Gate and Lotus Temple, window grids, a boundary wall, street lamps and ember ground. "Created by Ritesh Roshan" in the masthead of every page; the nav is Story and Method. Home opens with **The long shade** (`Ride.astro`): the KV plan's 85 neems replayed at 0, 1, 5, 10, 20 and 30 years, every year a full SOLWEIG and JOS-3 run (`future.json`). On wide screens the year and a 31-cell timeline stick on the left while the stage scrubs with the scroll and cools from warm black to green-black; each year's card carries its SOLWEIG map, the yard's band, a 100-cell shade waffle and the under-crown pair; then the cut ("She is still nine."), the six growth drawings to scale, a canopy bloom of 5,861 cells from 85 seeds, the vision, and a night grove (`grove.svg`). Phones and reduced motion get the same years as static cards. The stage shows the flat SOLWEIG maps until `public/media/future-ride.json` exists, then the 3D ride from `tools/three-d/render.py --future`. Then a cell-drawn Earth lit by the model's sun for the 1 pm hour (subsolar point from `neem_core.sun.subsolar_point`), a four-panel zoom (Delhi, one yard, one square metre, one child), a before/after slider of real SOLWEIG maps for the agent's plan, a pipeline strip naming the AWS tools, the city map with the hottest and coolest yards annotated, the twins and a searchable ranking. `/story` is the long-form writeup with live figures. Neem branches hang into the top corners and a schoolyard strip tops the footer (`tools/cell_art.py`). School pages: planner island (trees only on open ground, honest verify state on the static site), child chart. Every number is read from `src/data/*.json` or `public/twins/*`, written by `neem-data publish`.
- Palette: colour anchors and the UTCI heat-stress bands are separate (`neem_core.palette.BANDS`: 26 moderate, 32 strong, 38 very strong, 46 extreme), mirrored in `web/src/lib/palette.ts` and tested on both sides.
- `neem-data verify-plan`: re-runs every stored agent plan through SOLWEIG and keeps the field (`runs/{id}/{day}-plan`); it reproduced every stored verified number exactly. `publish` draws the plan map and writes `showcase.json`.
- `neem-data grow [school] --ages 1,10,20,30`: the stored plan's trees at each age (`neem_core.interventions.NEEM_BY_AGE`, our assumption inside published neem ranges), same weather, full SOLWEIG, into `runs/{id}/{day}-plan-y{age}`; `publish` turns them into `future.json` and `map-1pm-y{age}.png`.
- Infra: `infra/Dockerfile` (one image; Lambda Web Adapter; awslambdaric), `infra/compose.yaml` (LocalStack 4.14 + bootstrap + api + 2 workers), `infra/template.yaml` (**SAM**: S3, DynamoDB, SQS+DLQ, API Lambda + HTTP API, worker Lambda on SQS, rank + collect Lambdas, Step Functions Distributed Map), `infra/sam-env.json`, `infra/events/*.json`. `sam validate` passes; `sam build` succeeds.
- Tests: 64 fast Python (property, differential, contract against moto, Cedar policy and HTTP, palette bands, publish, tree growth), 4 slow SOLWEIG, 19 TypeScript. ADRs 0001 to 0010. Lighthouse on the production build: home 97/100/100/100 with the ride, story and method 100 across, school 98/100/100/100. QA sweep: no horizontal scroll or console errors from 360 to 2560 px.

## Results (real runs)

- Showcase day Mon 27 April 2026, Delhi max 42.2 C. City ranking: 766 schools ok (26 no open ground); canopy vs heat r = -0.95; 34% of yards spend over a quarter of the morning in extreme heat stress.
- Twins near DTU: KV Sector 25 Rohini (`osm-w1321574340`, 2.9 km), School of Specialised Excellence (`osm-w1096874054`), MCD Primary (`osm-w1158946096`), Rani Chenamma SKV (`osm-w78786253`).
- Agent plans, budget Rs 3,00,000, SOLWEIG-verified at 1 pm (yard mean, today -> plan; child core rise today -> plan):
  - KV Sector 25: 85 neems, Rs 2,97,500: 46.6 -> 44.8 C; 0.93 -> 0.82 C.
  - SoSE: 85 neems, Rs 2,97,500: 46.6 -> 43.5 C; 0.93 -> 0.76 C.
  - MCD Primary: 62 neems + 3x3 m sail, Rs 2,33,200: 46.6 -> 43.1 C; 0.92 -> 0.75 C.
  - Rani Chenamma: 85 neems, Rs 2,97,500: 45.6 -> 44.2 C; 0.86 -> 0.78 C.
- KV plan grown (`neem-data grow`), yard at 1 pm / shade of the morning / child rise / under the new crowns vs the same cells today: year 1 46.6 C / 22% / 0.93 C / 46.7 vs 47.5; year 5 44.8 / 57% / 0.82 / 42.7 vs 47.4; year 10 44.2 / 67% / 0.80 / 42.2 vs 47.3; year 20 43.9 / 72% / 0.79 / 42.1 vs 47.3; year 30 43.7 / 75% / 0.78 / 42.1 vs 47.2, 5,861 m2 of crown.

## In progress / known issues

- SAM on LocalStack works end to end (11 Oct): `just sam-build` (fixed by a root `.dockerignore`; SAM was tarring the whole 6.5 GB repo), then `just seed; just sam-worker` takes the demo job queued -> done in 225 s on CPU (the worker timeout is now 900 s, queue visibility 960 s), `just sam-rank` returns `ok`, and `just sam-api` serves `/health` and `/schools`. Step Functions on LocalStack is not yet tried.
- T0 preview error where a design acts is about 4 to 5 C at midday (exact elsewhere); the UI states the band, and verified agent plans show preview vs physics (e.g. 45.3 vs 44.8).
- Overture heights: about 0.5% coverage; footprint prior elsewhere.
- LocalStack pinned to 4.14 (last open-source; 2026.x requires a token).

## Pending, in order

1. **Video (3 min)**, see `docs/VIDEO.md`. Run `just seed` first so `just sam-worker` visibly takes the demo job from queued to done; start `just sam-api` early (warm containers are on).
2. **Make the repo public**, then submit: repo link, video link and the writeup in `docs/SUBMISSION.md`.
3. **Builder Center blog**: `docs/BLOG.md` (the same story as `/story`, with images from the live site).
4. 3D moonshot (`recon/`, ADR 0007): needs a 60 to 90 s video of an empty courtyard. Not started.
5. After the hackathon: rotate the Resend key; optionally try Step Functions on LocalStack.

## How to resume

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;C:\Users\roshh\AppData\Local\Microsoft\WinGet\Packages\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\bun-windows-x64;C:\Program Files\Docker\Docker\resources\bin;$env:Path"
$env:PYTHONUTF8 = "1"
just check; just check-web
uv run neem-api            # local API on :8000
cd web; bun run dev        # site on :4321
just plan osm-w1321574340  # Strands planner (Ollama must be running)
```

For `sam build`, point `DOCKER_CONFIG` at a folder containing `{}` (the user's Docker config references a gcloud credential helper that is not installed). `data/` (the lake) is gitignored and regenerates from public sources (see the README).
