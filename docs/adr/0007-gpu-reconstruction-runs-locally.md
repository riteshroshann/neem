# 7. Phone-video reconstruction runs locally on the GPU

Date: 2026-10-10
Status: accepted

## Context

Many Indian schools have no building heights in open data. A 60 to 90 second phone video of an empty courtyard can be turned into a 3D model and a surface model. Gaussian splatting needs a CUDA GPU. New AWS accounts start with zero GPU quota, and a quota increase can take days.

## Decision

Run reconstruction in a Docker container with GPU passthrough on the laptop (RTX 4050, 6 GB): COLMAP for camera poses, splatfacto for the Gaussian splat, then rasterise the dense points to a DSM and CDSM (vegetation split by an excess-green index on point colour). The splat is exported for the web viewer; the DSM feeds the scene builder. The same container can run on SageMaker once quota exists.

## Consequences

- No dependency on AWS GPU quota for the demo.
- 6 GB VRAM caps image resolution and Gaussian count; we downscale frames and cap the model size.
- Georeferencing uses three control points matched to the Overture footprint; scale comes from the footprint, not the phone.
