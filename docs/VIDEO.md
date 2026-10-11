# Demo video: the pitch, under 3 minutes

The full shooting script, with what to do on screen for every line, the founder's story, the engineering behind each claim and likely questions, is the PDF "Neem: the pitch". The narration below is about 440 words, which runs to 2:45 at a confident pace.

## Tabs, in order (Ctrl+1 to Ctrl+5)

1. https://neem-lemon.vercel.app/
2. https://neem-lemon.vercel.app/school/osm-w1321574340
3. https://neem-lemon.vercel.app/#pipeline-title
4. https://github.com/riteshroshann/neem/blob/main/infra/template.yaml#L40
5. https://neem-lemon.vercel.app/

## Narration

I'm Ritesh Roshan. I grew up in Cuttack, in Odisha, where the air quality index can drop to 20 or 30. Then I came to Delhi to study at Amrita, and my phone showed a different world. I kept thinking about the kids growing up here, and the decades ahead of all of us. On the 27th of April, Delhi hit 42 degrees, and a government schoolyard in Rohini felt like 47. Everyone knows trees are the answer. Nobody knows where to plant them, or what one is worth to a child. So I built Neem, named for the tree that thrives in dry ground and is in full leaf by May.

This is that school, Kendriya Vidyalaya: 46.6 degrees at 1 pm, and a child loses nearly a litre of water before lunch. Neem's AI planner put 85 neems here, inside a three-lakh budget. Now watch them grow. Every stop is a full physics simulation of the same heatwave day, so the trees are the only variable. Year five: out of extreme heat stress. Year thirty: a grove, and the ground beneath it feels like 42 where today it's 47.

A one-metre heat twin, hour by hour. SOLWEIG traces every shadow, how much sky each square metre sees, and the heat thrown back by baked ground and walls. One run takes four seconds on a GPU, too slow for a mouse, so the browser predicts only the change, in ten milliseconds, and keeps physics' exact value everywhere else. The agent's plan, verified by SOLWEIG: 44.8. And this is a child's body, minute by minute.

The data streams from AWS Open Data on S3: of Overture's 512 building files, Neem reads only the three that touch Delhi. Three rules hold it together. Every number traces back to a run anyone can repeat. The language model chooses, physics reports: a Strands agent makes the plan, and its tools place every tree, hold the budget and call SOLWEIG. And the code that runs on my laptop is the code built for AWS; only an endpoint changes.

This SAM template is the service: S3, DynamoDB, SQS feeding Lambda workers, and a Step Functions Distributed Map written to rank every school, a hundred at a time. SAM CLI and LocalStack run the API and workers here, and Cedar guards it: nobody, not even an admin, approves a plan physics hasn't verified.

Across 766 Delhi yards, the leafier the yard, the cooler it runs: a correlation of minus 0.95. Schools come first, because the kids who water these saplings will plant the rest. Terraforming, the gentle way. I'm Ritesh Roshan. Start with the children.

## Upload

Upload to YouTube as Unlisted, then paste the link into the submission form.

**Title:** Neem: heat twins for Delhi schoolyards | WeMakeDevs x AWS Environmental Hacks

**Description:** Neem works out how hot every square metre of a Delhi schoolyard feels to a child on a heatwave day, plants neem trees with physics, and grows them for thirty years. Built with SOLWEIG, a child body twin, Strands Agents, AWS SAM, LocalStack and Cedar. Live: https://neem-lemon.vercel.app. Code: https://github.com/riteshroshann/neem. Built by Ritesh Roshan.
