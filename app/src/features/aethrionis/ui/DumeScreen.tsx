import { useCallback, useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";

import { cn } from "@/shared/lib/cn";
import { type WorkPackage, dumeApi } from "../lib/dumeApi";
import { CommandBar } from "./CommandBar";
import { DumePanel } from "./DumePanel";

/**
 * The commissioning surface: every work package on the left, the selected
 * package's records on the right.
 *
 * The list is ordered by wave and then by id, which is the order the plan puts
 * them in. It is deliberately not ordered by recency: a package that failed and
 * is waiting matters more than one that was merely touched, and sorting by
 * "latest" hides exactly that.
 */

const STATE_TONE: Record<string, string> = {
  ACCEPTED: "text-emerald-400",
  ACCEPTANCE_READY: "text-emerald-300",
  TECH_COMPLETE: "text-teal-300",
  VERIFYING: "text-sky-300",
  CODE_REVIEW: "text-sky-300",
  SPEC_REVIEW: "text-sky-300",
  EXECUTING: "text-violet-300",
  PLANNED: "text-zinc-300",
  PACKAGED: "text-zinc-400",
  READY: "text-zinc-400",
  FAILED: "text-red-400",
  RETRY: "text-amber-300",
  BLOCKED: "text-amber-400",
};

export function DumeScreen({ wpId }: { wpId?: string }) {
  const [packages, setPackages] = useState<WorkPackage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal: AbortSignal) => {
    try {
      const { packages: rows } = await dumeApi.packages(signal);
      if (!signal.aborted) {
        setPackages(rows);
        setError(null);
      }
    } catch (cause) {
      if (!signal.aborted) {
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = setInterval(() => void load(controller.signal), 5000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [load]);

  return (
    <div className="flex h-full min-h-0">
      <div className="flex w-[320px] shrink-0 flex-col border-r border-border/60">
        <div className="border-b border-border/60 px-4 py-3">
          <h1 className="text-sm font-semibold">Commissioning</h1>
          <p className="mt-1 text-[11px] text-muted-foreground">
            DUM-E builds AETHRIONIS, then stops. It is a harness, not a component.
          </p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {error && (
            <p className="p-4 text-xs text-destructive">
              Work packages could not be read: {error}
            </p>
          )}
          {!error && packages === null && (
            <p className="p-4 text-xs text-muted-foreground">Reading DUM-E…</p>
          )}
          {packages?.length === 0 && (
            <p className="p-4 text-xs text-muted-foreground">
              No work package has started.
            </p>
          )}
          {packages?.map((row) => (
            <Link
              key={row.wp_id}
              to="/dume"
              search={{ wp: row.wp_id }}
              className={cn(
                "block border-b border-border/40 px-4 py-2.5 hover:bg-accent/40",
                row.wp_id === wpId && "bg-accent/60",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px]">{row.wp_id}</span>
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wide",
                    STATE_TONE[row.state] ?? "text-muted-foreground",
                  )}
                >
                  {row.state.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs text-foreground">
                {row.title}
              </p>
              {row.waiting_on.length > 0 && (
                <p className="mt-0.5 text-[10px] text-amber-400">
                  waiting on {row.waiting_on.join(", ")}
                </p>
              )}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-hidden">
          <DumePanel wpId={wpId} />
        </div>
        <CommandBar />
      </div>
    </div>
  );
}
