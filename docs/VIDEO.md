# Demo video: under 3 minutes

A walk through the live site, read aloud while recording. About 430 words of narration, which runs about 2:50 at an easy pace. Every number is from a real run.

## Before recording

1. Open three tabs: [neem-lemon.vercel.app](https://neem-lemon.vercel.app), [the docs](https://neem-lemon.vercel.app/docs#flow), and [the SAM template's Distributed Map](https://github.com/riteshroshann/neem/blob/main/infra/template.yaml#L150-L171).
2. Scroll the home page's ride once so the 3D film is cached, then reload and go back to the top.
3. Browser full screen at 1920 x 1080 and 100% zoom (wider than 1000 px, so the ride plays as a film). Hide the bookmarks bar and turn notifications off.
4. Record screen and microphone with OBS Studio, or the Snipping Tool's recorder (Win + Shift + R).
5. Upload to YouTube as **Unlisted** and paste the link into the form.

## Script

**0:00 · About.** *Home page, the Earth turning.*
"On the 27th of April, the air in Delhi hit 42 degrees. In the open yard of a government school in Rohini, a child felt 47. I'm Ritesh Roshan, and this is Neem. It shows how hot every square metre of a schoolyard feels, and how many trees it takes to cool it down."

**0:20 · Thirty years forward.** *Click "Ride thirty years forward". Scroll slowly; rest a beat on Today, Year 5 and Year 30.*
"This is Kendriya Vidyalaya. Today the yard feels like 46.6 degrees at 1 pm, and a nine-year-old loses nearly a litre of water before lunch. Neem's planner put 85 neem trees here, inside a three-lakh budget, and then grew them. Every year you see is a full physics run on the same hot day, so the trees are the only thing that changes. By year five, the yard is out of extreme heat stress. By year thirty, the ground under the crowns feels like 42, where today it's 47."

**0:58 · Why schools.** *Keep scrolling, past the trees, to "Start with the children."*
"Why schools? Children feel the heat first. Every school has open ground and a gate that opens each morning, and the kids who water these saplings will plant the streets and parks next."

**1:12 · The city.** *Scroll on to the map, "Where the yards run hottest".*
"Neem modelled 766 Delhi schoolyards. One in three spends over a quarter of the morning in extreme heat, and tree canopy explains almost all of the difference."

**1:25 · The planner.** *Just below the map, under "Open a heat twin", click Kendriya Vidyalaya. Click 7 am, then 1 pm. Click two spots in the red yard. Click "Load this plan", then scroll to the child's chart.*
"This is that school at one metre, hour by hour. Click to plant a tree, and the shade updates in about ten milliseconds, right in the browser. This is the agent's plan: 85 neems, checked by SOLWEIG, the radiation model climate researchers use. At 1 pm the yard drops from 46.6 to 44.8. And this is the child: core temperature, minute by minute, through assembly and recess."

**1:55 · Tech stack, architecture and AWS.** *Switch to the docs tab ("The whole thing in one breath"), then to the GitHub tab and scroll through the highlighted Distributed Map.*
"Under the hood: open data in, physics out. Buildings and tree heights come straight from AWS Open Data on S3. SOLWEIG runs on my laptop GPU, about four seconds a school. This SAM template describes the service on AWS: Lambda for the API, SQS for the worker queue, DynamoDB, S3, and a Step Functions Distributed Map that ranks every school in parallel. LocalStack runs all of it on my laptop. Cedar guards who runs physics and who approves a plan. A Strands agent writes the plans, but only its tools produce numbers."

**2:35 · What I learned.** *Back to the home page.*
"What I learned: let the AI choose, and let physics report. Running on LocalStack caught a bug my mocks missed: DynamoDB rejects floats. Neem: start with the children. I'm Ritesh Roshan, and the code is open."

## YouTube title and description

**Title:** Neem: heat twins for Delhi schoolyards | WeMakeDevs x AWS Environmental Hacks

**Description:**

Neem works out how hot every square metre of a Delhi schoolyard feels to a child on a heatwave day, plants neem trees with physics, and grows them for thirty years. Built with SOLWEIG, a child body twin, Strands Agents, AWS SAM, LocalStack and Cedar.

Live: https://neem-lemon.vercel.app
Code: https://github.com/riteshroshann/neem

Built by Ritesh Roshan.
