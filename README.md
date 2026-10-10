# Neem

A physics-grade heat twin for Delhi schoolyards. Neem computes how hot every square metre of a school feels to a child on a heatwave day, simulates a nine-year-old's core temperature and water loss through the school day, and lets a planner drag trees onto the yard and see the effect instantly, then verified by a full radiation model.

## Quick start

```sh
uv sync
just check
just scene <school_id>
```

## How it works

- **Surface model from open data on AWS.** Overture building heights, Meta's canopy height map and the Copernicus DEM are rasterised to a 1 m surface model for each school.
- **SOLWEIG** (UMEP's Rust implementation, on GPU) computes shadows, sky view factor and the full shortwave and longwave budget, giving mean radiant temperature and UTCI hour by hour.
- **Two fidelity tiers.** A fast shadow caster, calibrated per school against SOLWEIG, previews a design in milliseconds; SOLWEIG verifies it in seconds.
- **Child body twin.** The JOS-3 thermoregulation model, scaled to a child, turns the heat field into core temperature and sweat loss for a real schedule.
- **City scale.** The same handler ranks every school in Delhi, on a local process pool or a Step Functions Distributed Map.

Design notes live in [docs/architecture.md](docs/architecture.md) and [docs/adr](docs/adr).

## License

Copyright (C) 2026 Ritesh Roshan. GPL-3.0-or-later, because SOLWEIG is.

Engineered by Ritesh Roshan.
