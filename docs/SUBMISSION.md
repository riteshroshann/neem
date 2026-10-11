# Neem

A heat model of Delhi's schoolyards for the WeMakeDevs x AWS Environmental Hacks, Heat & Water track (Build It). Live at [neem-lemon.vercel.app](https://neem-lemon.vercel.app); code at [github.com/riteshroshann/neem](https://github.com/riteshroshann/neem). Submitted by Ritesh Roshan.

## The problem

On Monday 27 April 2026, the hottest school day before Delhi's summer vacation, the air reached 42.2 °C. A child in an open yard feels more than the air. At 1 pm, at the centre of the open yard of Kendriya Vidyalaya Sector 25 in Rohini, the air was 42.1 °C, but sun and heat from baked ground and walls pushed the mean radiant temperature to 67.2 °C. With 14% humidity and a 3.6 m/s wind, that feels like 47.3 °C (UTCI), past the 46 °C threshold for extreme heat stress. Neem's model of a nine-year-old on the morning shift there loses 877 ml of water by 12:45. A principal can plant trees or put up shade, but on a fixed budget, without knowing which square metres matter or what a tree is worth in degrees.

## What Neem does

Neem shows how hot a schoolyard feels to a child on a heatwave day, and what trees and shade would change, before anyone digs. It ranks 766 Delhi schoolyards by heat, from SOLWEIG runs at 2 m for 9 am, 11 am and 1 pm. Four government schools near Delhi Technological University (DTU) have full heat twins at 1 m, hour by hour from 7 am to 1 pm, each with a child body model and a browser planner for trees and shade sails. A planning agent proposes a plan within a budget, and SOLWEIG verifies it.

The home page opens on an Earth drawn in square cells and lit by the sun exactly as the model used it for the 1 pm hour (12:30 IST, from the repository's NOAA solar code): straight overhead just off the Karnataka coast, 75° above the yard in Rohini. It zooms from Delhi to one yard, one square metre and one child, then a slider compares SOLWEIG's maps of that yard before and after the agent's 85 neems. A long-form story at [/story](https://neem-lemon.vercel.app/story) walks through all of it with live figures.

## How it works

The data is open, and mostly on AWS. Buildings come from Overture Maps on S3: only 3 of the release's 512 files overlap Delhi, so Neem picks them from the STAC catalogue and loads 1.9 million footprints in two minutes. Canopy heights come from Meta and WRI on AWS Open Data, ground from the Copernicus 30 m DEM, schools from OpenStreetMap and weather from ERA5 via Open-Meteo.

The physics is SOLWEIG, the UMEP radiation model used in urban climate research. For a person at each grid cell it traces sun and shadow from buildings and crowns, sky light, and heat radiated by ground and walls, giving mean radiant temperature and then UTCI. A school takes about 4 seconds on the laptop GPU.

The child is JOS-3, a 17-segment thermoregulation model scaled to a nine-year-old (1.32 m, 28 kg) and walked minute by minute through the morning shift. Its set points come from adults, so Neem reports the core rise above rest and the water lost, as indicative figures.

The planner is a Strands agent on qwen3 4B, served by Ollama on the laptop. The model picks how many trees, which species and whether a sail is worth it; its tools choose where, enforce the budget, preview and verify, so every figure in its answer comes from a tool.

Verification has two tiers. The browser preview recasts shadows and predicts the change from the physics run in about 10 ms. Untouched squares keep SOLWEIG's value; where a design acts, the preview can be off by about 4 to 5 °C at midday, and the page says by how much. "Verify with physics" re-runs SOLWEIG and the child's day on a worker. Tests pin the tiers together: the shadow caster matches SOLWEIG on more than 97% of cells, and the preview's mean error against SOLWEIG stays under 1 °C on a design it has never seen. All 63 fast and 4 slow SOLWEIG tests in Python and 15 TypeScript tests pass.

The architecture is a lake of plain files on S3, queried in place with DuckDB, plus a FastAPI service, an SQS worker and job state in DynamoDB. AWS sits behind ports whose boto3 adapters take an endpoint URL, so the same code runs against LocalStack. The public site is static Astro on Vercel.

## The four AWS open-source tools

Strands Agents SDK runs the planner in `packages/neem-agent/src/neem_agent/planner.py`: five tools bound to one school, with `qwen3:4b` through Strands' Ollama provider. The budget is a hard limit inside `plant_trees`, and if the model skips `verify`, the code runs it.

AWS SAM CLI builds the stack described in `infra/template.yaml`: an S3 lake, a DynamoDB jobs table, SQS with a dead-letter queue, an API Lambda, a worker Lambda on SQS, and a Step Functions Distributed Map that ranks schools on up to 100 Lambdas at once, all built from one Dockerfile. `sam local invoke` runs the worker and ranking functions on the laptop with events from `infra/events/`, and `sam local start-api` serves the API: the worker takes the demo job from queued to done against LocalStack with numbers identical to the in-process run.

LocalStack 4.14, the last open-source release, emulates S3, SQS, DynamoDB and Step Functions (`infra/compose.yaml`, `just localstack`), and `packages/neem-worker/src/neem_worker/bootstrap.py` seeds the lake into its S3. Running the stack locally caught two bugs the in-process moto tests had missed: DynamoDB rejects float attributes, and SAM's emulator needs a root build user.

Cedar, through `cedarpy` in `packages/neem-api/src/neem_api/authz.py`, enforces `packages/neem-api/src/neem_api/policies/neem.cedar`. Anyone may view twins and request verification within 200 trees, 40 sails and 20 jobs per identity per hour. Only a school's own planner may approve its plan, and a `forbid` stops everyone, administrators included, from approving one SOLWEIG has not verified.

## Results

Neem modelled 766 schoolyards for 27 April 2026; 26 more had no open ground to model. Tree canopy and yard heat correlate at r = −0.95, and one yard in three (34%) spends more than a quarter of the school morning above 46 °C UTCI. Under the same weather, mean yard heat at 9 am, 11 am and 1 pm runs from 39.0 to 44.7 °C, median 42.0 °C.

The agent planned each twin within ₹3,00,000, and SOLWEIG verified every plan:

| School | Plan | Cost | Yard at 1 pm | Child's peak core rise | Water lost by 12:45 |
|---|---|---|---|---|---|
| Kendriya Vidyalaya, Sector 25, Rohini | 85 neems | ₹2,97,500 | 46.6 → 44.8 °C | 0.93 → 0.82 °C | 877 → 843 ml |
| School of Specialised Excellence | 85 neems | ₹2,97,500 | 46.6 → 43.5 °C | 0.93 → 0.76 °C | 875 → 822 ml |
| MCD Primary School | 62 neems, one 3 × 3 m sail | ₹2,33,200 | 46.6 → 43.1 °C | 0.92 → 0.75 °C | 867 → 820 ml |
| Rani Chenamma Sarvodaya Kanya Vidyalaya | 85 neems | ₹2,97,500 | 45.6 → 44.2 °C | 0.86 → 0.78 °C | 852 → 829 ml |

At 1 pm, the same 85 neems take 3.1 °C off the School of Specialised Excellence, with 5,691 m² of open ground, and 1.8 °C off Kendriya Vidyalaya, with 11,397 m². MCD Primary had room for only 62 neems, so the agent added a sail. The preview's 1 pm yard mean landed within 0.6 °C of SOLWEIG in all four plans, and the new `neem-data verify-plan` command re-ran every stored plan through SOLWEIG and reproduced every number exactly.

## Open data and licences

Neem is GPL-3.0-or-later, copyright 2026 Ritesh Roshan, because SOLWEIG and UMEP are GPL-3.0. It builds on pythermalcomfort and JOS-3 (MIT), Overture Maps (ODbL), Meta and WRI canopy height (CC BY 4.0), OpenStreetMap (ODbL), the Copernicus DEM and ERA5 via Open-Meteo. It stores no personal data.

## Run it locally

You need uv, just, Bun, Docker, SAM CLI and Ollama; SOLWEIG falls back to the CPU without a GPU. Developed on Windows 11 with PowerShell 7.

```sh
uv sync; just check
cd web; bun install; bun run dev           # the site on :4321
```

From the repository root, rebuild the lake (`data/`, not in git) from public sources, then plan, verify and serve:

```sh
just ingest; uv run neem-data weather; just rank
just scene osm-w1321574340; uv run neem-data twin osm-w1321574340
ollama pull qwen3:4b; just plan osm-w1321574340
uv run neem-data verify-plan; just publish
uv run neem-api                            # :8000, for "Verify with physics"
```

The serverless stack, on LocalStack:

```sh
docker network create neem; just localstack; docker network connect neem neem-localstack
just seed; just sam-build; just sam-worker
```

## What is next

Measured building heights come first: only about 0.5% of Delhi's buildings carry a height or floor count in open data. The `recon/` package turns a phone video of an empty yard into measured heights on the 1 m grid, with VGGT; running it on real yards is next. Then more 1 m twins, a body model built for children, and the Ship It path: the same SAM template on AWS, with Cognito identities for Cedar.

## AI tools used

Claude Code was used as a coding assistant during development. The product itself uses Strands Agents with Ollama running qwen3:4b locally for the planning agent.
