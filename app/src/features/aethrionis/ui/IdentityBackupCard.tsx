import * as React from "react";

import {
  createNcryptsecBackup,
  saveNcryptsecCopy,
  verifyNcryptsecBackup,
} from "@/shared/api/tauriIdentity";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";

/**
 * A way to keep the identity key.
 *
 * The key on this machine is what makes messages this workspace signed
 * attributable to it. There is no server that can reissue it and no
 * administrator who can recover it: lose the machine without a copy and the
 * identity is gone, along with the ability to prove that anything it signed
 * was signed by it.
 *
 * The backup is NIP-49: the key encrypted under a passphrase, so the file is
 * safe to keep somewhere the machine is not. The passphrase is not stored — a
 * passphrase kept beside the file it protects is decoration — which also means
 * a forgotten one cannot be recovered either.
 *
 * Verification is offered next to it because a backup that was never checked
 * is a belief, not a backup: it decrypts locally and reports only the public
 * half and whether it matches the identity in use.
 */
export function IdentityBackupCard() {
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [note, setNote] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const [checkText, setCheckText] = React.useState("");
  const [checkPassword, setCheckPassword] = React.useState("");
  const [checkNote, setCheckNote] = React.useState<string | null>(null);

  async function save() {
    setError(null);
    setNote(null);
    if (password.length < 8) {
      setError("Use at least eight characters. This is the only thing standing between the file and the key.");
      return;
    }
    if (password !== confirm) {
      setError("The two passphrases differ. A backup encrypted under a typo cannot be opened later.");
      return;
    }
    setBusy(true);
    try {
      const ncryptsec = await createNcryptsecBackup(password);
      const path = await saveNcryptsecCopy(ncryptsec);
      setNote(
        path === null
          ? "Nothing was written — the save was cancelled."
          : `Written to ${path}. Keep it somewhere this machine is not, and remember the passphrase: it is not stored anywhere.`,
      );
      setPassword("");
      setConfirm("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    setCheckNote(null);
    setBusy(true);
    try {
      const result = await verifyNcryptsecBackup(
        checkText.trim(),
        checkPassword,
      );
      setCheckNote(
        result.matchesCurrentIdentity
          ? `Opens, and it is this workspace's identity (${result.npub.slice(0, 16)}…).`
          : `Opens, but it is a different identity (${result.npub.slice(0, 16)}…) — not the one in use here.`,
      );
    } catch (cause) {
      setCheckNote(
        `Could not open it: ${cause instanceof Error ? cause.message : String(cause)}`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Back up this identity</h2>
        <p className="text-xs text-muted-foreground">
          The key lives on this machine and nowhere else. Nothing can reissue
          it, so a copy kept elsewhere is the only way back from a lost disk.
          The file is encrypted under a passphrase that is never stored.
        </p>
        <Input
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Passphrase"
          type="password"
          value={password}
        />
        <Input
          onChange={(event) => setConfirm(event.target.value)}
          placeholder="Passphrase again"
          type="password"
          value={confirm}
        />
        <span>
          <Button disabled={busy} onClick={() => void save()} size="sm">
            Save a copy
          </Button>
        </span>
        {error ? <p className="text-xs text-destructive">{error}</p> : null}
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Check a backup</h2>
        <p className="text-xs text-muted-foreground">
          A backup nobody has opened is a belief. This decrypts it here and
          reports only the public half and whether it is the identity in use.
        </p>
        <Input
          onChange={(event) => setCheckText(event.target.value)}
          placeholder="ncryptsec1…"
          value={checkText}
        />
        <Input
          onChange={(event) => setCheckPassword(event.target.value)}
          placeholder="Its passphrase"
          type="password"
          value={checkPassword}
        />
        <span>
          <Button
            disabled={busy || !checkText.trim()}
            onClick={() => void check()}
            size="sm"
            variant="secondary"
          >
            Check it
          </Button>
        </span>
        {checkNote ? (
          <p className="text-xs text-muted-foreground">{checkNote}</p>
        ) : null}
      </section>
    </div>
  );
}
