/**
 * The rendered AETHRIONIS mark, for the surfaces where the mark is the subject.
 *
 * Not tinted and not `currentColor`: it is a rendered object with its own
 * lighting, and recolouring it produces something that is neither the mark nor
 * a glyph. Small placements use `AethrionisMark` instead.
 */
export function AethrionisAppmark({
  className,
  alt = "AETHRIONIS",
}: {
  className?: string;
  alt?: string;
}) {
  return <img alt={alt} className={className} src="/aethrionis.png" />;
}
