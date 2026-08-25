/**
 * The AETHRIONIS mark as a monochrome glyph.
 *
 * The brand asset is a rendered 3-D form on a plinth: right for an application
 * icon, wrong for a 16-pixel glyph sitting in a line of text. This is the same
 * geometry reduced to what survives at that size — the outer delta, the inner
 * counterform, and the descending point — painted in `currentColor` so it takes
 * the colour of whatever it is placed in.
 *
 * Where the mark is the subject rather than a bullet — the splash, onboarding —
 * the rendered asset is used instead. See `AethrionisAppmark`.
 */
export function AethrionisMark({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={["aethrionis-mark", className].filter(Boolean).join(" ")}
      viewBox="0 0 100 92"
      fill="none"
      stroke="currentColor"
      strokeWidth={7}
      strokeLinejoin="round"
      strokeLinecap="round"
    >
      {/* Outer delta */}
      <path d="M50 6 L94 86 L6 86 Z" />
      {/* Inner counterform: the crossbar and the descending point */}
      <path d="M31 62 L50 62" />
      <path d="M50 36 L67 66 L50 82 L33 66 Z" fill="currentColor" stroke="none" />
    </svg>
  );
}
