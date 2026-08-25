import * as React from "react";

import { cn } from "@/shared/lib/cn";
import { Input } from "@/shared/ui/input";
import { type CommandResult, type Vocabulary, dume } from "../lib/dumeApi";

/**
 * Commanding DUM-E from the interface.
 *
 * There is no shell here. What can be typed is a fixed vocabulary, and a
 * message that is not in it is refused with the whole list rather than guessed
 * at. That refusal is the feature: an interface that tries to interpret an
 * unrecognised instruction is an interface that can be talked into something.
 *
 * The class of every answer is shown. "I looked something up" and "I changed
 * something" should not look the same, and the verb alone does not always say
 * which it was.
 */

const CLASS_TONE: Record<string, string> = {
  READ: "border-zinc-500/40 text-zinc-400",
  CONTROL: "border-sky-500/40 text-sky-300",
  HUMAN_DECISION: "border-amber-500/50 text-amber-300",
  DANGEROUS_ACTION: "border-red-500/50 text-red-300",
};

export function CommandBar() {
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<CommandResult | null>(null);
  const [vocabulary, setVocabulary] = React.useState<Vocabulary>([]);
  const [showVocabulary, setShowVocabulary] = React.useState(false);

  React.useEffect(() => {
    void dume
      .vocabulary()
      .then(({ commands }) => setVocabulary(commands))
      .catch(() => {
        // The bar still works without it; the list is a convenience, and the
        // gateway refuses anything outside the vocabulary either way.
      });
  }, []);

  const send = React.useCallback(async (command: string) => {
    if (!command.trim()) return;
    setBusy(true);
    try {
      setResult(await dume.run(command));
      setText("");
    } catch (cause) {
      setResult({
        outcome: "ERROR",
        reply: cause instanceof Error ? cause.message : String(cause),
      });
    } finally {
      setBusy(false);
    }
  }, []);

  const confirm = React.useCallback(async (ref: string) => {
    setBusy(true);
    try {
      setResult(await dume.confirm(ref));
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <div className="border-t border-border/60 bg-background/80 px-4 py-3">
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void send(text);
        }}
      >
        <Input
          disabled={busy}
          onChange={(event) => setText(event.target.value)}
          placeholder="status · next · show WP-001 · retry WP-002 · decide WP-001 …"
          value={text}
        />
        <button
          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setShowVocabulary((open) => !open)}
          type="button"
        >
          {vocabulary.length || "?"}
        </button>
      </form>

      {showVocabulary && (
        <div className="mt-3 max-h-56 overflow-y-auto rounded-md border border-border/60 p-2">
          {vocabulary.map((entry) => (
            <button
              className="block w-full rounded px-2 py-1 text-left hover:bg-accent/50"
              key={entry.command}
              onClick={() => {
                setText(entry.command + (entry.parameters.length ? " " : ""));
                setShowVocabulary(false);
              }}
              type="button"
            >
              <span className="font-mono text-xs">
                {entry.command}{" "}
                <span className="text-muted-foreground">
                  {entry.parameters.map((p) => `<${p}>`).join(" ")}
                </span>
              </span>
              <span
                className={cn(
                  "ml-2 rounded-full border px-1.5 text-[10px] uppercase",
                  CLASS_TONE[entry.class],
                )}
              >
                {entry.class.replace("_", " ")}
              </span>
              <span className="block text-[11px] text-muted-foreground">
                {entry.summary}
              </span>
            </button>
          ))}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-md border border-border/60 p-3">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {result.outcome.replace(/_/g, " ").toLowerCase()}
            </span>
            {"class" in result && (
              <span
                className={cn(
                  "rounded-full border px-1.5 text-[10px] uppercase",
                  CLASS_TONE[result.class],
                )}
              >
                {result.class.replace("_", " ")}
              </span>
            )}
            {"audit" in result && (
              <span
                className="ml-auto font-mono text-[10px] text-muted-foreground"
                title="Every command is recorded under this reference."
              >
                {result.audit}
              </span>
            )}
          </div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-5">
            {result.reply}
          </pre>
          {result.outcome === "AWAITING_CONFIRMATION" && (
            <button
              className="mt-2 rounded-md bg-destructive px-3 py-1.5 text-xs text-destructive-foreground"
              disabled={busy}
              onClick={() => void confirm(result.confirmation_ref)}
              type="button"
            >
              Confirm {result.action}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
