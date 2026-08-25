import * as React from "react";
import { openUrl } from "@tauri-apps/plugin-opener";

import { Button } from "@/shared/ui/button";
import { type DeviceCode, membership } from "../lib/dumeApi";

/**
 * Membership, established by proving a GitHub account.
 *
 * The device flow is used rather than a browser redirect because this is a
 * desktop application: a redirect needs a loopback server and a registered
 * callback, and both are more moving parts than a code typed once.
 *
 * What this screen establishes is *membership*, not identity. The identity is
 * the key already on this machine and is not affected by anything that happens
 * here — including a refusal. That is deliberate: removing someone from the
 * project and destroying their identity must not be the same operation.
 */
export function GithubMembership({
  onAdmitted,
}: {
  onAdmitted: (result: { relayUrl: string; code: string; login: string }) => void;
}) {
  const [device, setDevice] = React.useState<DeviceCode | null>(null);
  const [status, setStatus] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [unconfigured, setUnconfigured] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const begin = React.useCallback(async () => {
    setBusy(true);
    setError(null);
    setUnconfigured(false);
    try {
      const next = await membership.begin();
      setDevice(next);
      setStatus("Waiting for GitHub…");
      void openUrl(next.verification_uri).catch(() => {
        // Opening the browser is a convenience. The code and the address are
        // both on screen, so a failure here costs a copy and paste, not the
        // flow.
      });
    } catch (cause) {
      const failure = cause as Error & { unconfigured?: boolean };
      setUnconfigured(Boolean(failure.unconfigured));
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }, []);

  React.useEffect(() => {
    if (!device) return;
    let cancelled = false;
    const deadline = Date.now() + device.expires_in * 1000;

    const tick = async () => {
      if (cancelled) return;
      if (Date.now() > deadline) {
        setDevice(null);
        setError("The code expired before it was entered.");
        return;
      }
      try {
        const verdict = await membership.poll(device.device_code);
        if (cancelled) return;
        if (verdict.status === "pending") {
          window.setTimeout(tick, device.interval * 1000);
          return;
        }
        if (verdict.status === "refused") {
          setDevice(null);
          // Naming who was refused is what lets the operator tell a typo from
          // a missing roster entry.
          setError(
            `${verdict.login} is not admitted to this deployment: ${verdict.reason}.`,
          );
          return;
        }
        if (!verdict.invite) {
          setDevice(null);
          setError(
            `${verdict.login} is admitted, but the relay has no invite to hand out.`,
          );
          return;
        }
        const url = new URL(verdict.invite);
        onAdmitted({
          relayUrl: url.searchParams.get("relay") ?? verdict.relay_ws,
          code: url.searchParams.get("code") ?? "",
          login: verdict.login,
        });
      } catch (cause) {
        if (cancelled) return;
        setDevice(null);
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    };

    const timer = window.setTimeout(tick, device.interval * 1000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [device, onAdmitted]);

  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Membership</h1>
      <p className="mt-3 max-w-[540px] text-sm leading-6 text-muted-foreground">
        Your identity is the key on this machine and stays that way. To join this
        workspace, prove a GitHub account that its roster admits.
      </p>

      {device ? (
        <div className="mt-8 flex flex-col items-center gap-3">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Enter this code at {device.verification_uri}
          </p>
          <code className="rounded-lg border border-border bg-muted px-6 py-3 font-mono text-3xl tracking-[0.3em]">
            {device.user_code}
          </code>
          <p className="text-xs text-muted-foreground">{status}</p>
          <button
            className="text-xs text-muted-foreground underline"
            onClick={() => void openUrl(device.verification_uri)}
            type="button"
          >
            Open GitHub again
          </button>
        </div>
      ) : (
        <Button className="mt-8" disabled={busy} onClick={() => void begin()}>
          {busy ? "Asking GitHub…" : "Continue with GitHub"}
        </Button>
      )}

      {error ? (
        <div className="mt-6 max-w-[560px] text-sm">
          <p className="text-destructive">{error}</p>
          {unconfigured ? (
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              This deployment has not registered an OAuth app yet. Create one
              under GitHub → Settings → Developer settings → OAuth Apps with the
              device flow enabled, then write its client id, and the logins or
              organisation it admits, to{" "}
              <code>~/.dume/secrets/github-membership.json</code>.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
