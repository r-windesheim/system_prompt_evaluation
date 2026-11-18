// One place for motion. Reduced motion: <MotionConfig reducedMotion="user"> drops transforms, the CSS in
// globals.css turns transitions off, and height animations swap in `instant` (MotionConfig does not cover them).

export const ease = [0.16, 1, 0.3, 1] as [number, number, number, number];

/** an opened part unfolding, "More detail" unfolding */
export const unfold = { duration: 0.36, ease };
/** a margin note arriving; `i` staggers them down the page */
export const arrive = (i: number) => ({ duration: 0.45, ease, delay: Math.min(i * 0.07, 0.6) });

export const instant = { duration: 0 } as const;
