import { useCallback, useEffect, useState } from "react";
import { cn } from "@/shared/lib/cn";
import { type PackageDetail, type StateSummary, dumeApi } from "../lib/dumeApi";

/**
 * DUM-E's records, shown as records.
 *
 * Everything on this panel came from DUM-E's own store. None of it came from a
 * channel, and none of it can be changed from one. That is the whole point of
 * the panel existing separately from the conversation rather than as messages
 * inside it: a reader who cannot tell a claim from a record will eventually
 * treat one as the other, and every prohibited authority transfer starts there.
 */

const GATE_TONE: Record<string, string> = {
  MERGE_ELIGIBLE: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  BLOCKED: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  REFUSED: "border-red-500/50 bg-red-500/10 text-red-300",
};

function Bead({ tone, children }: { tone?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tone ?? "border-zinc-500/40 bg-zinc-500/10 text-zinc-300",
      )}
    >
      {children}
    </span>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {k}
      </span>
      <span className="text-right text-xs text-foreground">{v}</span>
    </div>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-border/60 px-4 py-3 last:border-b-0">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
      {note && <p className="mt-2 text-[11px] text-muted-foreground">{note}</p>}
    </section>
  );
}

export function DumePanel({ wpId }: { wpId?: string }) {
  const [summary, setSummary] = useState<StateSummary | null>(null);
  const [detail, setDetail] = useState<PackageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      try {
        const state = await dumeApi.state(signal);
        if (signal.aborted) return;
        setSummary(state);
        const target = wpId ?? state.current?.wp_id;
        setDetail(target ? await dumeApi.package(target, signal) : null);
        setError(null);
      } catch (cause) {
        if (signal.aborted) return;
        // Shown, not swallowed. An empty panel would read as "nothing to
        // report", which is a claim nobody made.
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    },
    [wpId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = setInterval(() => void load(controller.signal), 5000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [load]);

  if (error) {
    return (
      <div className="p-4 text-xs text-destructive">
        <p className="font-medium">DUM-E state could not be read.</p>
        <p className="mt-1 text-muted-foreground">{error}</p>
        <p className="mt-2 text-muted-foreground">
          This panel is blank because the read failed, not because there is
          nothing to report.
        </p>
      </div>
    );
  }

  if (!summary) {
    return <div className="p-4 text-xs text-muted-foreground">Reading DUM-E…</div>;
  }

  const pkg = detail?.package ?? summary.current;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">DUM-E</h2>
          {summary.last_run && (
            <Bead tone={GATE_TONE[summary.last_run]}>{summary.last_run}</Bead>
          )}
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">
          The commissioning harness. Nothing said in a channel moves a package.
        </p>
      </div>

      {!pkg ? (
        <div className="p-4 text-xs text-muted-foreground">
          No work package has started.
        </div>
      ) : (
        <>
          <Section title="Work package">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-xs">{pkg.wp_id}</span>
              <Bead>{pkg.state.replace(/_/g, " ")}</Bead>
            </div>
            <p className="text-xs text-foreground">{pkg.title}</p>
            <Row k="Wave" v={pkg.wave} />
            {pkg.waiting_on.length > 0 && (
              <Row k="Waiting on" v={pkg.waiting_on.join(", ")} />
            )}
          </Section>

          {detail?.candidate && (
            <Section
              title="Candidate"
              note={
                detail.candidate.stale
                  ? "This evidence describes an earlier revision. It has been superseded."
                  : undefined
              }
            >
              <Row
                k="Revision"
                v={<span className="font-mono">{detail.candidate.candidate}</span>}
              />
              <Row k="Discipline" v={detail.candidate.discipline} />
              <Row k="Tests" v={detail.candidate.tests} />
              <Row k="Files changed" v={detail.candidate.files} />
              <Row
                k="Worktree"
                v={<span className="font-mono text-[11px]">{detail.candidate.worktree}</span>}
              />
            </Section>
          )}

          {detail && detail.reviews.length > 0 && (
            <Section
              title="Reviews"
              note="A reviewer's answer is a record about a candidate. It is not a verdict on the package."
            >
              {detail.reviews.map((review) => (
                <div key={review.kind} className="mb-2 last:mb-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">{review.kind}</span>
                    <Bead
                      tone={
                        review.verdict === "PASS"
                          ? GATE_TONE.MERGE_ELIGIBLE
                          : GATE_TONE.REFUSED
                      }
                    >
                      {review.verdict}
                    </Bead>
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {review.reason}
                  </p>
                  {review.findings > 0 && (
                    <p className="mt-0.5 text-[11px] text-amber-400">
                      {review.findings} finding
                      {review.findings === 1 ? "" : "s"}
                    </p>
                  )}
                </div>
              ))}
            </Section>
          )}

          {detail?.verification && (
            <Section
              title="Verification"
              note={
                detail.verification.fresh_checkout
                  ? "Re-run from a fresh checkout, in a directory the implementer never touched."
                  : "NOT a fresh checkout — this ran where the candidate was written."
              }
            >
              <Row k="Exit code" v={detail.verification.exit} />
              <Row k="Suite" v={detail.verification.summary} />
              <Row
                k="Candidate"
                v={
                  <span className="font-mono text-[11px]">
                    {detail.verification.candidate.slice(0, 12)}
                  </span>
                }
              />
            </Section>
          )}

          {detail?.gate && (
            <Section
              title="Gate"
              note="Decided by a deterministic check over recorded evidence. No model was reachable when it ran."
            >
              <div className="mb-2">
                <Bead tone={GATE_TONE[detail.gate.verdict]}>
                  {detail.gate.verdict}
                </Bead>
              </div>
              {(detail.gate.checks ?? []).map((check) => (
                <Row
                  key={check.name}
                  k={check.name.replace(/_/g, " ")}
                  v={
                    <span
                      className={check.passed ? "text-emerald-400" : "text-red-400"}
                      // The question, not just the answer: a gate whose checks
                      // cannot be read is a gate that has to be trusted.
                      title={`${check.question}\n\n${check.detail}`}
                    >
                      {check.passed ? "passed" : "failed"}
                    </span>
                  }
                />
              ))}
            </Section>
          )}

          {detail && detail.findings.length > 0 && (
            <Section title="Findings">
              {detail.findings.map((finding, index) => (
                <p key={index} className="mb-1 text-[11px] last:mb-0">
                  <span className="mr-1.5 font-semibold text-amber-400">
                    {finding.severity}
                  </span>
                  {finding.summary}
                </p>
              ))}
            </Section>
          )}
        </>
      )}

          {detail && detail.evidence.length > 0 && (
            <Section
              title="Evidence"
              note="A zero-byte artefact is evidence of nothing, and is marked as such."
            >
              {detail.evidence.map((file) => (
                <Row
                  key={file.name}
                  k={file.name}
                  v={
                    file.empty ? (
                      <span className="text-red-400">empty</span>
                    ) : (
                      <span className="text-muted-foreground">
                        {file.bytes.toLocaleString()} bytes
                      </span>
                    )
                  }
                />
              ))}
            </Section>
          )}

          {detail && detail.history.length > 0 && (
            <Section title="History">
              {detail.history.map((step) => (
                <div key={`${step.at}:${step.to}`} className="mb-1.5 last:mb-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs">
                      {step.from.replace(/_/g, " ").toLowerCase()} →{" "}
                      <b>{step.to.replace(/_/g, " ").toLowerCase()}</b>
                    </span>
                    <time className="text-[10px] text-muted-foreground">
                      {step.at.slice(0, 16).replace("T", " ")}
                    </time>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {step.actor} — {step.reason}
                  </p>
                </div>
              ))}
            </Section>
          )}

      <Section title="Runtimes" note="Availability is not eligibility.">
        {summary.runtimes.map((runtime) => (
          <Row
            key={runtime.runtime_id}
            k={runtime.runtime_id}
            v={
              <span
                className={
                  runtime.status === "AVAILABLE"
                    ? "text-emerald-400"
                    : "text-muted-foreground"
                }
                title={
                  runtime.qualified.length
                    ? `Qualified for: ${runtime.qualified.join(", ")}`
                    : "Not qualified for any role"
                }
              >
                {runtime.status}
              </span>
            }
          />
        ))}
      </Section>
    </div>
  );
}
