# Neem: status and handoff

Last updated: Sat 10 Oct 2026, about 8:15 PM IST. Deadline: **Sun 11 Oct 2026, 8:00 PM IST** (WeMakeDevs x AWS Environmental Hacks, Heat & Water track). Submission = public repo + 3-minute YouTube video (AWS tooling visible on screen) + short writeup listing AI tools used.

Track chosen: **Build It** (AWS open-source tools, on the machine, no AWS account). Tools in use: **Strands Agents SDK, SAM CLI, LocalStack, Cedar**. Ship It (real AWS deploy) is optional later and needs an account; `infra/template.yaml` is ready for it.

## Live

- Site: **https://neem-lemon.vercel.app** (Vercel project `neem`, account riteshroshann). Static Astro + one Vercel Function `web/api/email.ts` (Resend).
- Repo: github.com/riteshroshann/neem (private; make public before submitting).
- Resend sends only to the account address (no verified domain): `RESEND_TO` = riteshroshansahoo01@gmail.com. Key lives in `web/.env.local` (gitignored) and Vercel env. Rotate it after the hackathon: it was pasted in chat.

## Done

- Physics core (`neem-core`): scenes, interventions, sun, numba shadow caster, SOLWEIG engine (GPU), anchored T0 preview, JOS-3 child twin (rise above rest), schedules, exposure, palette.
- Data (`neem-data`): OSM schools, Overture (3 of 512 files via STAC), Meta canopy v2, Copernicus DEM, ERA5 via Open-Meteo, scene builder, twin runner, city batch, design verification, publish (ranking, thumbnails, static twin files, agent plans), S3-backed lake for Lambda (`sync_from_s3`, `upload`), Lambda entry points for the ranking map (`lambda_rank.handler`, `collect`).
- API (`neem-api`): FastAPI, job ports (files+threads / DynamoDB+SQS), **Cedar** authorization (`policies/neem.cedar` + schema): anyone explores; verification has a size and rate budget; only a school's planner approves, only verified plans. Token identity table (`NEEM_DEV_TOKENS`) stands in for Cognito.
- Worker (`neem-worker`): SQS loop + Lambda handler; bootstrap creates table, queue, lake bucket, seeds the lake, queues a demo job.
- Planner agent (`neem-agent`): **Strands Agents** + Ollama `qwen3:4b` on the GPU. Tools: brief, plant_trees (hottest-first placement, budget enforced in the tool), add_shade_sail, preview, verify. Plans saved to `lake/plans/` and published.
- Web (`web/`): editorial site (index with dot map and ranking, school pages with the planner island, method page). T0 ported to TypeScript and pinned to Python by a shared-fixture differential test. "Load Neem's plan" shows the agent's verified plan on the public site.
- Infra: `infra/Dockerfile` (one image; Lambda Web Adapter; awslambdaric), `infra/compose.yaml` (LocalStack 4.14 + bootstrap + api + 2 workers), `infra/template.yaml` (**SAM**: S3, DynamoDB, SQS+DLQ, API Lambda + HTTP API, worker Lambda on SQS, rank + collect Lambdas, Step Functions Distributed Map), `infra/sam-env.json`, `infra/events/*.json`. `sam validate` passes; `sam build` succeeds.
- Tests: 47 fast Python (property, differential, contract against moto, Cedar policy and HTTP), 4 slow SOLWEIG, 9 TypeScript. ADRs 0001 to 0010.

## Results (real runs)

- Showcase day Mon 27 April 2026, Delhi max 42.2 C. City ranking: 766 schools ok (26 no open ground); canopy vs heat r = -0.95; 34% of yards spend over a quarter of the morning in extreme heat stress.
- Twins near DTU: KV Sector 25 Rohini (`osm-w1321574340`, 2.9 km), School of Specialised Excellence (`osm-w1096874054`), MCD Primary (`osm-w1158946096`), Rani Chenamma SKV (`osm-w78786253`).
- Agent plans, budget Rs 3,00,000, SOLWEIG-verified at 1 pm (yard mean, today -> plan; child core rise today -> plan):
  - KV Sector 25: 85 neems, Rs 2,97,500: 46.6 -> 44.8 C; 0.93 -> 0.82 C.
  - SoSE: 85 neems, Rs 2,97,500: 46.6 -> 43.5 C; 0.93 -> 0.76 C.
  - MCD Primary: 62 neems + 3x3 m sail, Rs 2,33,200: 46.6 -> 43.1 C; 0.92 -> 0.75 C.
  - Rani Chenamma: 85 neems, Rs 2,97,500: 45.6 -> 44.2 C; 0.86 -> 0.78 C.

## In progress / known issues

- `sam local invoke WorkerFunction` against LocalStack: first run reached the handler and correctly reported a batch failure (missing `libexpat`); image now installs `libexpat1 libgomp1`; rerun was building at handoff. Check: `just sam-build; just localstack; just seed; just sam-worker`.
- T0 preview error where a design acts is about 4 to 5 C at midday (exact elsewhere); the UI states the band, and verified agent plans show preview vs physics (e.g. 45.3 vs 44.8).
- Overture heights: about 0.5% coverage; footprint prior elsewhere.
- LocalStack pinned to 4.14 (last open-source; 2026.x requires a token).

## Pending, in order

1. Confirm the SAM worker run end to end; optionally `sam local start-api` and a Step Functions run on LocalStack.
2. 3D moonshot (`recon/`, ADR 0007): needs the user's 60 to 90 s video of an empty courtyard. Not started.
3. Video (3 min): problem 20 s (headline, 47 C), product 90 s (map, plant, verify, child chart, agent plan), tooling 40 s (Strands agent run in terminal, Cedar policy + 403, `sam local invoke` against LocalStack), impact 30 s (r = -0.95, 766 schools). Writeup listing AI tools. Builder Center blog.
4. Make the repo public; polish README with the vibe skill.

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
