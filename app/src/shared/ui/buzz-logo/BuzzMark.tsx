import { AethrionisMark } from "./AethrionisMark";

/**
 * The application mark, as a monochrome glyph.
 *
 * Upstream's bee, drawn here as AETHRIONIS's delta. The name and the call sites
 * are upstream's — ten files render this — and renaming them would be a
 * hundred-line diff across modules the fork otherwise does not touch, which is
 * a hundred lines of future merge conflict for a symbol nobody types.
 */
export function BuzzMark({ className }: { className?: string }) {
  return <AethrionisMark className={className} />;
}
