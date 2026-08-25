import * as React from "react";

import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { type Roster, roster as rosterApi } from "../lib/dumeApi";

/**
 * GitHub membership, as an operator setting.
 *
 * This is where "who may connect to this workspace" is answered. It is not
 * where identity is managed: the identity is a key on this machine and nothing
 * here can create, change or revoke it. Removing somebody from the roster stops
 * them joining and leaves everything they ever signed verifiable, which is the
 * whole reason the two are separate.
 */
export function GithubSettingsCard() {
  const [roster, setRoster] = React.useState<Roster | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [clientId, setClientId] = React.useState("");
  const [org, setOrg] = React.useState("");
  const [require, setRequire] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const next = await rosterApi.read();
      setRoster(next);
      setClientId(next.client_id ?? "");
      setOrg(next.org ?? "");
      setRequire(next.require);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const decide = async (login: string, verdict: "approve" | "deny") => {
    setBusy(true);
    try {
      await rosterApi.decide(login, verdict);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      await rosterApi.configure(clientId.trim(), org.trim(), require);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 px-6 py-6">
      <header>
        <h2 className="text-lg font-semibold">GitHub membership</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Who may connect to this workspace. Your identity is a key on this
          machine and nothing here touches it — removing somebody from the
          roster stops them joining and leaves everything they signed
          verifiable.
        </p>
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="space-y-3">
        <h3 className="text-sm font-medium">OAuth app</h3>
        {roster && !roster.configured ? (
          <p className="text-xs leading-5 text-muted-foreground">
            Not configured yet. Create an OAuth app under GitHub → Settings →
            Developer settings → OAuth Apps, tick <b>Enable Device Flow</b>, and
            paste its client id here. There is no client secret: the device flow
            does not use one, which is why it suits an application that ships to
            every machine.
          </p>
        ) : null}
        <label className="block text-xs text-muted-foreground" htmlFor="gh-client">
          Client ID
        </label>
        <Input
          id="gh-client"
          onChange={(event) => setClientId(event.target.value)}
          placeholder="Ov23li…"
          value={clientId}
        />
        <label className="block text-xs text-muted-foreground" htmlFor="gh-org">
          Organisation (optional) — anyone whose membership is active is admitted
        </label>
        <Input
          id="gh-org"
          onChange={(event) => setOrg(event.target.value)}
          placeholder="my-org"
          value={org}
        />
        <Button disabled={busy || !clientId.trim()} onClick={() => void save()}>
          Save
        </Button>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">Sign-in</h3>
        <label className="flex items-start gap-3 rounded-md border border-border/60 px-3 py-2.5">
          <input
            checked={require}
            className="mt-0.5"
            disabled={busy || !roster?.configured}
            onChange={(event) => {
              const next = event.target.checked;
              setRequire(next);
              void (async () => {
                setBusy(true);
                try {
                  await rosterApi.configure(clientId.trim(), org.trim(), next);
                  await load();
                } catch (cause) {
                  setRequire(!next);
                  setError(cause instanceof Error ? cause.message : String(cause));
                } finally {
                  setBusy(false);
                }
              })();
            }}
            type="checkbox"
          />
          <span className="text-sm">
            Ask for a GitHub account when the application opens
            <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
              Off by default. On a machine you own, running a relay you run,
              being asked to prove an account before the workspace will open is
              a checkpoint with nobody on the other side of it. Turn it on when
              there is somebody to keep out. The roster below works either way —
              which is what makes this a switch rather than a migration.
            </span>
          </span>
        </label>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">Admitted</h3>
        {roster?.logins.length ? (
          <ul className="space-y-1 text-sm">
            {roster.logins.map((login) => (
              <li
                className="flex items-center justify-between rounded-md border border-border/60 px-3 py-1.5"
                key={login}
              >
                <span>{login}</span>
                <Button
                  disabled={busy}
                  onClick={() => void decide(login, "deny")}
                  size="sm"
                  variant="ghost"
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            Nobody by name. An empty roster with no organisation admits nobody —
            which is the right default, because a membership system that admits
            everyone until it is configured is not one.
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-medium">Waiting for a decision</h3>
        {roster?.pending.length ? (
          <ul className="space-y-1 text-sm">
            {roster.pending.map((entry) => (
              <li
                className="flex items-center justify-between rounded-md border border-border/60 px-3 py-1.5"
                key={entry.login}
              >
                <span>
                  {entry.login}
                  <span className="ml-2 text-xs text-muted-foreground">
                    asked {entry.first_asked.slice(0, 16).replace("T", " ")}
                  </span>
                </span>
                <span className="flex gap-2">
                  <Button
                    disabled={busy}
                    onClick={() => void decide(entry.login, "approve")}
                    size="sm"
                  >
                    Approve
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => void decide(entry.login, "deny")}
                    size="sm"
                    variant="ghost"
                  >
                    Deny
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            Nobody. Somebody who signs in and is turned away appears here, so a
            refusal is a decision you can make rather than a message you have to
            remember.
          </p>
        )}
      </section>
    </div>
  );
}
