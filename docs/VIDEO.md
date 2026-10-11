# Demo video: the pitch, under 3 minutes

A founder's pitch, recorded as a walk through the live site. It covers the form's four points: the project (0:00 to 1:49), tech stack and architecture (1:49), AWS (2:09), and learning and growth (2:32). About 430 words of narration; at a confident pace it ends near 2:55. If a take runs past 3:00, drop beat 4.

## Set up (10 minutes)

1. **Five tabs, in this order** (Ctrl+1 to Ctrl+5 jumps between them, even in full screen):
   1. https://neem-lemon.vercel.app/
   2. https://neem-lemon.vercel.app/school/osm-w1321574340
   3. https://neem-lemon.vercel.app/#pipeline-title
   4. https://github.com/riteshroshann/neem/blob/main/infra/template.yaml#L40
   5. https://neem-lemon.vercel.app/
2. **Warm up the site.** In tab 1, scroll all the way through the long shade so the 3D film loads, then reload. In tab 2, wait until the heat map has drawn. In tab 3, scroll up a touch if the header hides "How it runs".
3. **Screen.** Browser in full screen (F11), zoom 100% (Ctrl+0), notifications off, chat apps closed.
4. **Recorder.** Snipping Tool, already on Windows 11: Win+Shift+R, pick the whole screen, turn the microphone on. Or OBS Studio at 1920 x 1080, 30 fps.
5. **Voice.** Quiet room, mic a hand's width away, water nearby. Read the script aloud once with a timer before the first take.

## The pitch, beat by beat

### 1 · The hook (0:00) · tab 1, top of the home page

**Do:** Start recording, wait one second. Rest the cursor on the red "47." when you say it. On your name, glance the cursor to "Created by Ritesh Roshan".

**Say:** "On the 27th of April, Delhi hit **42** degrees. In a government schoolyard in Rohini, a nine-year-old felt **47**: extreme heat stress. Everyone knows trees are the answer. **Nobody knows where to plant them**, or what one tree is worth to a child, until five years too late. I'm Ritesh Roshan, and I built Neem to show that future **today**."

*Open strong, no "hi everyone". Half a beat of silence after "47".*

### 2 · The product, thirty years forward (0:23) · tab 1

**Do:** Click "Ride thirty years forward". Scroll a notch until the big "0" and the card "Nearly a litre before lunch" show. On "Now I scroll", roll the wheel steadily, about two notches a second. Pause on "The shade arrives" for year five, and on "A grove" for year thirty. End with the cursor on the "47.2 °C → 42.1 °C" chips.

**Say:** "This is Kendriya Vidyalaya today: **46.6** degrees at 1 pm, and a child loses nearly **a litre of water** before lunch. Neem's AI planner put **85 neem trees** here, inside a three-lakh budget. **Now I scroll, and they grow.** Each stop on this ride is a full physics simulation of that same heatwave day. Year five: out of extreme heat stress. Year thirty: **a grove**. Under those crowns it feels like **42**, where today it's **47**."

*This is the money shot. Let the film breathe; don't race the scroll.*

### 3 · Why schools (0:55) · tab 1

**Do:** Keep scrolling past the six trees drawn to scale, and stop on "Start with the children." with the three reasons in view. On "first ring", run the cursor along the line from "Schoolyards" to "A planet that grows its own shade".

**Say:** "Why schools first? Because children feel the heat **first**. Because every neighbourhood has a schoolyard. And because the kids who water these saplings grow up to plant the streets and the parks. Schoolyards are **the first ring**."

*Warmer and slower here. This is the why.*

### 4 · The evidence (1:09) · tab 1

**Do:** One smooth scroll past the quotes, "Terraforming, the gentle way" and the night grove, to the three big numbers. Hover 766, then "1 in 3", then 2.8 °C.

**Say:** "And it's not one school. Neem modelled **766** Delhi schoolyards. **One in three** spends over a quarter of the morning in extreme heat, and tree cover explains almost all of it: a correlation of **minus 0.95**."

### 5 · The planner (1:23) · Ctrl+2

**Do:** Scroll until the map and the hour tabs fill the screen. Click "7 am", then "1 pm". Click twice on the red open yard (not the white roofs). In the right column, click "Load this plan": 85 green rings fill the yard. Point at "46.6 → 44.8 °C". Scroll down to the child's chart.

**Say:** "This is the product: a **one-metre** heat twin of the school, hour by hour. I plant a tree, and the shade and the heat update in **ten milliseconds**, right in the browser. Here's the AI's plan, **verified by SOLWEIG**, the radiation model climate researchers use: the yard drops from 46.6 to **44.8**. And that's the child's body, minute by minute."

### 6 · Tech stack and architecture (1:49) · Ctrl+3

**Do:** "Open data in, verified physics out" with five stages. Move the cursor left to right across them as you name each one: AWS Open Data, S3 · DuckDB, SQS · Lambda, Strands Agents · Cedar.

**Say:** "Under the hood: **open data in, verified physics out.** Buildings and tree heights stream straight from **AWS Open Data on S3**. SOLWEIG runs in a queue worker, about **four seconds** a school on a laptop GPU. A **Strands** agent writes the plans, and **Cedar** decides who can verify and approve them."

### 7 · How I used AWS (2:09) · Ctrl+4

**Do:** The SAM template opens at line 40. Scroll down slowly as you name each resource: LakeBucket (S3), JobsTable (DynamoDB), JobsQueue (SQS), ApiFunction and WorkerFunction (Lambda), and stop on RankStateMachine, the Map with Mode: DISTRIBUTED.

**Say:** "This **SAM** template is the whole service on AWS: **S3** for the data lake, **DynamoDB** for jobs, **SQS** for the physics queue, **Lambda** for the API and the worker, and a **Step Functions Distributed Map** that ranks every school in parallel. It runs on my laptop with **SAM CLI and LocalStack**, and the same template is ready for AWS."

### 8 · What I learned, and the ask (2:32) · Ctrl+5

**Do:** The home page again, the Earth turning. Hands off the mouse. After the last line, hold two seconds, then stop recording.

**Say:** "What I learned: **let the AI choose, and let physics report.** Every number you saw comes from a run anyone can repeat. Neem has mapped **766** yards. India has nearly **fifteen lakh** schools. If you fund trees, run schools or build cities, **let's talk.** I'm Ritesh Roshan, and this is Neem. **Start with the children.**"

*Slow the last four words right down.*

## Teleprompter

On the 27th of April, Delhi hit 42 degrees. In a government schoolyard in Rohini, a nine-year-old felt 47: extreme heat stress. Everyone knows trees are the answer. Nobody knows where to plant them, or what one tree is worth to a child, until five years too late. I'm Ritesh Roshan, and I built Neem to show that future today.

This is Kendriya Vidyalaya today: 46.6 degrees at 1 pm, and a child loses nearly a litre of water before lunch. Neem's AI planner put 85 neem trees here, inside a three-lakh budget. Now I scroll, and they grow. Each stop on this ride is a full physics simulation of that same heatwave day. Year five: out of extreme heat stress. Year thirty: a grove. Under those crowns it feels like 42, where today it's 47.

Why schools first? Because children feel the heat first. Because every neighbourhood has a schoolyard. And because the kids who water these saplings grow up to plant the streets and the parks. Schoolyards are the first ring.

And it's not one school. Neem modelled 766 Delhi schoolyards. One in three spends over a quarter of the morning in extreme heat, and tree cover explains almost all of it: a correlation of minus 0.95.

This is the product: a one-metre heat twin of the school, hour by hour. I plant a tree, and the shade and the heat update in ten milliseconds, right in the browser. Here's the AI's plan, verified by SOLWEIG, the radiation model climate researchers use: the yard drops from 46.6 to 44.8. And that's the child's body, minute by minute.

Under the hood: open data in, verified physics out. Buildings and tree heights stream straight from AWS Open Data on S3. SOLWEIG runs in a queue worker, about four seconds a school on a laptop GPU. A Strands agent writes the plans, and Cedar decides who can verify and approve them.

This SAM template is the whole service on AWS: S3 for the data lake, DynamoDB for jobs, SQS for the physics queue, Lambda for the API and the worker, and a Step Functions Distributed Map that ranks every school in parallel. It runs on my laptop with SAM CLI and LocalStack, and the same template is ready for AWS.

What I learned: let the AI choose, and let physics report. Every number you saw comes from a run anyone can repeat. Neem has mapped 766 yards. India has nearly fifteen lakh schools. If you fund trees, run schools or build cities, let's talk. I'm Ritesh Roshan, and this is Neem. Start with the children.

## After recording

1. Check the length is under 3:00. Trim the first and last second in the Photos app if needed.
2. YouTube: Create, then Upload video. Pick the file and paste the title and description below. Choose "No, it's not made for kids", then Next, Next, and set visibility to **Unlisted**. Save, copy the link and paste it into the form.

**Title:** Neem: heat twins for Delhi schoolyards | WeMakeDevs x AWS Environmental Hacks

**Description:**

Neem works out how hot every square metre of a Delhi schoolyard feels to a child on a heatwave day, plants neem trees with physics, and grows them for thirty years. Built with SOLWEIG, a child body twin, Strands Agents, AWS SAM, LocalStack and Cedar.

Live: https://neem-lemon.vercel.app
Code: https://github.com/riteshroshann/neem

Built by Ritesh Roshan.
