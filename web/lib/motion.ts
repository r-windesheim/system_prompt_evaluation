// One place for motion: every animated element uses these presets.
// Reduced motion is handled globally by <MotionConfig reducedMotion="user">.

export const spring = {
  /** layout changes: sections folding, panels resizing */
  layout: { type: "spring", stiffness: 380, damping: 36, mass: 0.9 },
  /** data marks: effect dots and whiskers settling on new values */
  data: { type: "spring", stiffness: 220, damping: 24, mass: 1 },
  /** small UI acknowledgements: toggles, pills */
  snap: { type: "spring", stiffness: 600, damping: 40 },
} as const;

export const ease = {
  out: [0.16, 1, 0.3, 1] as [number, number, number, number],
};

/** Stagger for word-level text changes, capped so long responses don't crawl. */
export const wordDelay = (i: number) => Math.min(i * 0.006, 0.35);

/** Height/filter animations are not covered by MotionConfig's reducedMotion, so callers swap in this. */
export const instant = { duration: 0 } as const;
