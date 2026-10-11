# The air said 42 °C. The schoolyard said 47.

*How I built Neem: a heat map of 766 Delhi schoolyards, a body twin for the children who play in them, and a planning agent that has to prove its trees work.*

Ritesh Roshan · 11 October 2026 · read it with live figures at [neem-lemon.vercel.app/story](https://neem-lemon.vercel.app/story)

![The Earth drawn in square cells, lit by the sun as the model saw it for the 1 pm hour in Delhi](https://neem-lemon.vercel.app/og.png)

It's half past twelve on Monday 27 April 2026, the hottest school day Delhi had between April and the summer holidays. At Kendriya Vidyalaya, Sector 25, Rohini, the bell goes and the morning shift heads home across the open yard.

The weather report for that hour says 42 °C. Dry, too: 14% humidity and a 3.6 m/s breeze.

Nobody in that yard feels the air. They feel the sun, 75° up and leaving almost nowhere to hide, and the heat pouring back off ground and walls that have been soaking it up since sunrise. Add all of that together and the mean radiant temperature on one square metre at the centre of the yard is 67.2 °C. The feels-like temperature, the UTCI that heat-health researchers use, is 47.3 °C. Extreme heat stress starts at 46.

Now rewind to 7:30. Assembly in the yard. Class from 7:50. Recess at ten: half an hour of running about in the sun. Class again, then the walk home. Neem follows a nine-year-old through that morning minute by minute, and recess alone lifts their core temperature from 0.14 °C above rest to 0.93 °C. By 12:45 they have sweated and breathed out 877 ml of water. Nearly a litre, before lunch.

The teachers who stand in that yard know all this in their bones. What nobody has is an answer to the next question. If we plant trees, which ones, where, and how much cooler will it be? A neem costs about ₹3,500 and takes five years to grow a proper crown, which is a long time to wait to learn you planted it in the wrong spot. I built Neem so a school can find out first.

## Heat, the way a body feels it

A thermometer measures air. A body is busier than that: it soaks up direct sun, the glow of the sky and every warm surface in sight. So Neem runs SOLWEIG, the radiation model Fredrik Lindberg and colleagues built at the University of Gothenburg. For every square metre of a yard it works out where the sun falls, where buildings and tree crowns throw shade, how much sky each spot can see and how much heat the ground and walls give back. On my laptop's 6 GB GPU, one school takes about four seconds.

Everything it needs is open, and most of it already lives on AWS. Buildings come from Overture Maps: only 3 of the release's 512 files overlap Delhi, so Neem asks the STAC catalogue for those three and reads 1.9 million footprints in two minutes. Tree heights come from the canopy map Meta and WRI publish on AWS Open Data, the ground from Copernicus, the schools from OpenStreetMap's volunteers and the weather from ERA5 through Open-Meteo. This project is mostly their work, carefully rearranged.

## What 766 yards say

Then Neem ranks the city: 766 schoolyards, modelled at 2 m for 9 am, 11 am and 1 pm, in about ten minutes. Every yard sat under the same sky that Monday, so whatever separates them was built or planted there.

It's shade. The leafiest quarter of yards, with 68% tree cover over open ground, averaged 40.5 °C. The barest quarter, at 15%, averaged 43.3 °C. Across all 766, tree cover and yard heat correlate at r = −0.95. And one yard in three spent more than a quarter of the school morning above 46 °C.

## One square metre at a time

Four government schools near DTU get the full treatment: a heat twin at 1 m, hour by hour from 7 am to 1 pm. Open one and plant neem, peepal, jamun or amaltas, or rig up a shade sail, and the map changes under your cursor.

SOLWEIG can't keep up with a mouse, so the browser takes an honest shortcut. A TypeScript preview recasts the shadows and predicts the change from the physics in about ten milliseconds. Squares you haven't touched keep SOLWEIG's exact value, and where you plant, the page tells you how far off the preview might be. When you like what you see, "Verify with physics" hands the design to the real model.

The child is JOS-3, a 17-segment model of how a body keeps its temperature, from Yoshito Takahashi and colleagues, run through Federico Tartarini's pythermalcomfort and scaled to a 1.32 m, 28 kg nine-year-old. It was built from adults, so Neem reports the rise above the child's own resting state and says plainly that its numbers are indicative.

## An agent that has to show its work

The planner is a Strands agent running qwen3 4B through Ollama, on the same laptop. It gets a school, a budget and five tools, plus one rule I enforce in code: it doesn't get to make numbers up.

The model decides how many trees, which species and whether a sail is worth the money. The tools do the rest. They read the school's brief, plant on the hottest open ground a crown's width apart, add a sail, preview, and verify. The budget lives inside the planting tool, because a model can talk its way past a flag but not past a function that says no.

Small models wander, and this one did. Once it answered from imagination without calling a single tool. Once it sailed past the budget. Both are guarded now, and if it forgets to verify, the code verifies for it.

**Physics gets the last word.**

At KV Sector 25, with ₹3 lakh to spend, the agent planted 85 neems for ₹2,97,500. SOLWEIG checked the plan: at 1 pm the yard drops from 46.6 °C to 44.8 °C, the child's peak core rise from 0.93 °C to 0.82 °C, and the water lost from 877 to 843 ml. At the School of Specialised Excellence, where the open ground is half the size, the same 85 neems take 3.1 °C off.

![The yard at 1 pm today: nearly all of it in extreme heat stress](https://neem-lemon.vercel.app/twins/osm-w1321574340/map-1pm.png)

![The same yard with 85 neems: their shade breaks it into cooler pools](https://neem-lemon.vercel.app/twins/osm-w1321574340/map-1pm-plan.png)

## Thirty years forward

A tree planted today is a promise about a yard someone else's child will stand in. So Neem grows the plan: the same 85 neems at 1, 5, 10, 20 and 30 years, each age a full SOLWEIG and child-twin run on that same Monday in April, so the trees are the only thing that changes. How big a neem gets by each age is my assumption, inside published ranges.

The first year does nothing. The saplings are 2 m tall in their brick guards and the yard still feels like 46.6 °C. By year five the shade has arrived: the yard drops out of extreme heat stress to 44.8 °C, and under the crowns 1 pm feels like 42.7 °C where the same ground is 47.4 °C today. By year thirty the crowns cover 5,861 m², and the ground beneath them feels like 42.1 °C where it is 47.2 °C now.

The home page tells it as a ride you scroll through, the yard growing in 3D beside the numbers, and it ends on one line. Every year a new nine-year-old walks into that yard on the same hot day. Only the trees get older.

![The yard thirty years after planting: a closed grove of neems over cooler ground](https://neem-lemon.vercel.app/media/future-y30.jpg)

## Trust, then check again

Every number on the site has to trace back to a run I can repeat. Tests set independent pieces against each other: my shadow caster agrees with SOLWEIG on more than 97% of cells, and the preview's average error stays under 1 °C on a design it was never calibrated on. Those tests earned their keep. One caught SOLWEIG quietly rewriting the arrays it was handed. Another caught DynamoDB refusing floating-point numbers.

The last check is the simplest. A command called `verify-plan` runs every plan the agent has made through SOLWEIG again, from scratch. All four came back identical, down to the child's minute-by-minute core temperature.

## AWS open source, on one laptop

The hackathon's Build It track asks for AWS's open-source tools on your own machine, and Neem leans on four. Strands Agents runs the planner. AWS SAM describes the serverless shape, from the API and worker Lambdas to a Step Functions map that can rank schools on a hundred Lambdas at once, and runs those same functions locally. LocalStack plays S3, SQS, DynamoDB and Step Functions underneath. Cedar writes the rules down: anyone can explore, physics runs come with a fair-use budget, and nobody, not even an admin, can approve a plan that physics hasn't verified.

The home page opens on the Earth, drawn in the same square cells as the yard maps and lit by the sun as the model saw it that hour: straight overhead just off the Karnataka coast, near Bhatkal. From there it zooms to Delhi, to one yard, to one square metre and to one child.

## What's next

Open data knows the height of only about 0.5% of Delhi's buildings, so the next step is a phone: a short video of an empty yard, turned into measured heights on the same 1 m grid. After that, more schools, a body model built for children rather than scaled down from adults, and the same SAM template running on AWS for real.

If you teach in a yard like this, run a school or plant trees for a living, I'd love to know what Neem gets wrong. The code is open under GPL-3.0 at [github.com/riteshroshann/neem](https://github.com/riteshroshann/neem), and every plan on the site can be re-run.

85 neems. ₹2,97,500. 1.8 °C off a schoolyard at 1 pm. Every one of those numbers came out of a physics run, and every one comes back the same when you run it again.
