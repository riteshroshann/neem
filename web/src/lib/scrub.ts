// Scroll-driven playback: which frame of a clip a scroll position lands on.

/** The frame shown at progress `p` (0 to 1) in a clip of `frames` frames. */
export const frameAt = (p: number, frames: number) =>
  Math.min(frames - 1, Math.max(0, Math.round(p * (frames - 1))));
