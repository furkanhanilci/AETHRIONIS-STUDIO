/**
 * The ten message classes AETHRIONIS requires a message to declare.
 *
 * AETHRIONIS Studio has no equivalent and no reason to: it is a collaboration client, and a
 * message there is a message. AETHRIONIS's constraint is narrower — nothing said
 * in a channel constitutes a review, a verification or an acceptance, and the
 * only way to hold that line is for the sender to say what a message *is*
 * rather than leave a reader to infer it from the prose.
 *
 * The class travels in an `aethrionis-type` tag on the event. Reading it out of
 * the body would reintroduce exactly the inference this exists to prevent.
 */
export const MESSAGE_CLASSES = [
  "PROPOSAL",
  "CHALLENGE",
  "EVIDENCE",
  "REQUEST",
  "CORRECTION",
  "DISAGREEMENT",
  "CONSENSUS_CANDIDATE",
  "ABSTAIN",
  "STATUS",
  "BLOCKER",
] as const;

export type MessageClass = (typeof MESSAGE_CLASSES)[number];

export const TYPE_TAG = "aethrionis-type";
export const REF_TAG = "aethrionis-ref";

/** Classes that cannot be answered, tracked or closed without a subject. */
export const NEEDS_REFERENCE: ReadonlySet<string> = new Set([
  "CHALLENGE",
  "EVIDENCE",
  "CORRECTION",
  "DISAGREEMENT",
  "CONSENSUS_CANDIDATE",
]);

/** Classes that leave something open until somebody answers them. */
export const OPENS_A_QUESTION: ReadonlySet<string> = new Set([
  "CHALLENGE",
  "REQUEST",
  "DISAGREEMENT",
  "BLOCKER",
]);

type Tag = readonly string[];

/**
 * The declared class, or null.
 *
 * Null means the sender did not declare one — an ordinary AETHRIONIS Studio message, or one
 * from a client that knows nothing about AETHRIONIS. It is deliberately not
 * defaulted to STATUS: "nobody said" and "somebody said STATUS" are different
 * facts, and collapsing them would let an undeclared message pass for a
 * declared one.
 */
export function messageClass(tags: readonly Tag[] | undefined): MessageClass | null {
  const raw = tags?.find((tag) => tag[0] === TYPE_TAG)?.[1];
  if (!raw) return null;
  const upper = raw.toUpperCase();
  return (MESSAGE_CLASSES as readonly string[]).includes(upper)
    ? (upper as MessageClass)
    : null;
}

/** What this message says it is about. Empty is not an error here — only the
 *  sender's own client can refuse to send a CHALLENGE with no subject; by the
 *  time it is on the wire, showing it honestly is the most we can do. */
export function messageRefs(tags: readonly Tag[] | undefined): string[] {
  return (tags ?? [])
    .filter((tag) => tag[0] === REF_TAG && tag[1])
    .map((tag) => tag[1] as string);
}

/**
 * A message whose class demands a subject and does not have one.
 *
 * Surfaced rather than hidden: a challenge nobody can close is a defect in the
 * conversation, and the reader is the only one who can act on it.
 */
export function isUntethered(tags: readonly Tag[] | undefined): boolean {
  const klass = messageClass(tags);
  return klass !== null && NEEDS_REFERENCE.has(klass) && messageRefs(tags).length === 0;
}

/** Tag rows to attach when publishing. */
export function classTags(
  klass: MessageClass,
  refs: readonly string[] = [],
): string[][] {
  return [[TYPE_TAG, klass], ...refs.map((ref) => [REF_TAG, ref])];
}
