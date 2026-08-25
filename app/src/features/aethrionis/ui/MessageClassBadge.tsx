import { cn } from "@/shared/lib/cn";
import {
  type MessageClass,
  isUntethered,
  messageClass,
  messageRefs,
} from "../lib/messageClass";

/**
 * Colour carries the same distinction the class does: what a message *claims to
 * be*. It never says whether the claim was accepted — that is a record, and a
 * record is not rendered here.
 */
const TONE: Record<MessageClass, string> = {
  PROPOSAL: "border-sky-500/40 text-sky-300 bg-sky-500/10",
  CHALLENGE: "border-amber-500/40 text-amber-300 bg-amber-500/10",
  EVIDENCE: "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
  REQUEST: "border-violet-500/40 text-violet-300 bg-violet-500/10",
  CORRECTION: "border-orange-500/40 text-orange-300 bg-orange-500/10",
  DISAGREEMENT: "border-rose-500/40 text-rose-300 bg-rose-500/10",
  CONSENSUS_CANDIDATE: "border-teal-500/40 text-teal-300 bg-teal-500/10",
  ABSTAIN: "border-zinc-500/40 text-zinc-400 bg-zinc-500/10",
  STATUS: "border-zinc-500/30 text-zinc-400 bg-transparent",
  BLOCKER: "border-red-500/50 text-red-300 bg-red-500/10",
};

export function MessageClassBadge({
  tags,
  className,
}: {
  tags: readonly (readonly string[])[] | undefined;
  className?: string;
}) {
  const klass = messageClass(tags);
  // Undeclared is not STATUS. An ordinary AETHRIONIS Studio message, or one from a client
  // that knows nothing about AETHRIONIS, gets no badge rather than a wrong one.
  if (!klass) return null;

  const refs = messageRefs(tags);
  const untethered = isUntethered(tags);

  return (
    <span className={cn("inline-flex items-center gap-1.5 align-middle", className)}>
      <span
        className={cn(
          "rounded-full border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide",
          TONE[klass],
        )}
        title={`Declared as ${klass}. A declaration, not an authority: nothing said in a channel constitutes a review, a verification or an acceptance.`}
      >
        {klass.replace(/_/g, " ")}
      </span>
      {refs.length > 0 && (
        <span
          className="text-[10px] text-muted-foreground"
          title={refs.join("\n")}
        >
          re: {refs[0]}
          {refs.length > 1 ? ` +${refs.length - 1}` : ""}
        </span>
      )}
      {untethered && (
        <span
          className="rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-px text-[10px] font-medium text-red-300"
          title={`A ${klass} names no subject, so nobody can answer, track or close it.`}
        >
          no subject
        </span>
      )}
    </span>
  );
}
