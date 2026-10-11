# Demo video: 3 minutes

Record at 1920 x 1080, browser at 100% zoom, terminal font 16 pt. Speak slowly; every number below is from a real run.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | neem-lemon.vercel.app, the headline | "On 27 April 2026 the air in Delhi reached 42 degrees. In the open yard of a government school in Rohini, it felt like 47. That's the heat a child stands in at assembly." |
| 0:15–0:30 | Click "See all 766 yards": the city map | "Neem modelled 766 school grounds across Delhi with SOLWEIG, the radiation model urban climate researchers use. One yard in three spends more than a quarter of the morning in extreme heat stress. And one thing explains the difference almost entirely: tree canopy. The correlation is minus 0.95." |
| 0:30–0:40 | Ranking table, search "Kendriya", open KV Sector 25 | "Every school has a heat map. Four near DTU have a full one-metre heat twin." |
| 0:40–1:00 | Planner: scrub 7 am → 1 pm, hover the yard, plant a few neems, watch the number move | "This is every square metre of the school, hour by hour. Plant a neem and the shade and the heat update in about ten milliseconds, in the browser. Where I plant, it tells me how far the preview can be off." |
| 1:00–1:20 | Click "Verify with physics" (local stack running), show the verified line; then the child chart | "Verify sends the design to the full radiation model, about ten seconds on the GPU. And this is the child: a nine-year-old's core temperature, minute by minute, through assembly, recess and the walk home. 877 millilitres of water lost by 12:45." |
| 1:20–1:45 | Terminal: `just plan osm-w1321574340` (run beforehand, replay the output) then "Load this plan" and the 3D view | "Nobody should place 85 trees by hand. A Strands agent, running on a local open model, decides how many and which species; its tools decide where, enforce the budget and verify with SOLWEIG. 85 neems, two lakh ninety-seven thousand rupees: the yard at 1 pm drops from 46.6 to 44.8." |
| 1:45–2:20 | Terminal and editor: `infra/template.yaml` (scroll the Distributed Map), `just sam-worker` against LocalStack, then `neem.cedar` and a 403 from an oversized design | "It's built on AWS open source. SAM describes the serverless stack: an API on Lambda, a worker on SQS, and a Step Functions Distributed Map that ranks every school in parallel. It runs on this laptop with SAM CLI against LocalStack. Cedar decides who may run physics and who may approve a school's plan; even an admin can't approve one that physics hasn't verified." |
| 2:20–3:00 | Back to the home page, "Ride thirty years forward": scroll slowly from year 0 to year 30, hold on "She is still nine.", then the GitHub repo | "Then we grew the plan. Every year here is a full SOLWEIG run on that same hot Monday, so the trees are the only change. By year five the yard is out of extreme heat stress. By year thirty the crowns cover 5,861 square metres, and the ground under them feels like 42.1 degrees where today it's 47.2. Every year a new nine-year-old walks into this yard. Only the trees get older. Built by Ritesh Roshan. The code is open." |

## Before recording

1. `just localstack`, `just seed`, `uv run neem-api`, `cd web; bun run dev`, Ollama running.
2. Run `just plan osm-w1321574340` once so the output is ready to show.
3. Keep the browser window at least 1000 px wide so the ride plays as a film (narrower windows show it as stills). Scroll the ride slowly: each year's card stays up while the film rests on that year.
4. Close notifications; hide the bookmarks bar.
