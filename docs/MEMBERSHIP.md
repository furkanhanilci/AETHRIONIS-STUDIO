# Identity, membership and admission

Three things, kept apart, because they fail differently.

| | what it is | how it is lost |
|---|---|---|
| **Identity** | a key held on the operator's machine | losing the key; nothing resets it |
| **Membership** | a GitHub account in this deployment's roster | being removed from the roster |
| **Admission** | a relay invite, minted once the two are bound | the invite expiring or being revoked |

Merging them is the failure this design exists to avoid. If membership *were*
the identity, then removing somebody from the project and destroying their
identity would be the same operation — an ordinary personnel change becomes
unrecoverable, and every message they ever signed becomes unverifiable.

## What happens on first run

1. The application creates an identity key on the machine. Nothing is sent
   anywhere and no service issues it. This is `ActorIdentity` — one of the six
   objects AETHRIONIS keeps distinct, and not the same thing as the role held,
   the persona spoken through, or the runtime that answers.
2. The gateway is asked whether this deployment has a roster.
   - **No roster** — the relay's standing invite is used and the application
     joins. Correct for a single-operator deployment: there is nobody to check
     against, and asking would be theatre.
   - **A roster** — membership is proved through a GitHub account.
3. On admission, the invite is redeemed and the workspace opens.

A refusal names who was refused. Without that, an operator cannot tell a typo
from a missing roster entry.

## Configuring the roster

Membership needs a GitHub OAuth app, because proving an account means asking
GitHub, and GitHub needs to know who is asking. It takes about two minutes and
nothing is published.

1. GitHub → **Settings** → **Developer settings** → **OAuth Apps** → **New OAuth App**.
   - *Application name*: `AETHRIONIS Studio`
   - *Homepage URL*: anything — `https://github.com/<you>` is fine
   - *Authorization callback URL*: anything — the device flow does not use it
2. Open the app and tick **Enable Device Flow**. This is the part that matters:
   without it GitHub refuses the device request.
3. Copy the **Client ID**. There is no client secret to copy: the device flow
   does not use one, which is exactly why it suits a desktop application — a
   secret shipped to every machine is not a secret.
4. Write `~/.dume/secrets/github-membership.json`:

```json
{
  "client_id": "Ov23li...",
  "logins": ["furkanhanilci"],
  "org": null
}
```

   - `logins` — accounts admitted by name.
   - `org` — a GitHub organisation; anyone whose membership is **active** is
     admitted. Pending invitations are not: an invitation nobody accepted is not
     a membership. Requesting an organisation also asks GitHub for the
     `read:org` scope; a roster of plain logins asks for nothing beyond the
     identity the flow already establishes.
   - Both may be set. Either alone is enough.

An empty roster admits nobody. That is deliberate: a membership system that
admits everyone until it is configured is not a membership system.

5. `chmod 600 ~/.dume/secrets/github-membership.json`, and keep it out of the
   repository. The file lives on ext4 rather than DATADRIVE1 because NTFS
   silently discards `chmod` (ADR-0007).

## What the token can do

The GitHub token never reaches the interface. The gateway uses it to read one
login — and, when the roster names an organisation, one membership state — and
then drops it. It is never stored.
