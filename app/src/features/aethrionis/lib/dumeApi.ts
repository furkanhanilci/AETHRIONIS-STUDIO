/**
 * DUM-E's canonical state, read from DUM-E — never from the relay.
 *
 * The client already reads the conversation from the relay. It must not read
 * state from there too. A message *about* a verdict and a verdict are different
 * objects, and the moment a client cannot tell them apart, `verdict_from_text`
 * is available to anyone who can type a convincing sentence. Everything here
 * comes from DUM-E's own store over a read-only localhost endpoint, and is
 * rendered as a record rather than as a message.
 *
 * Nothing in this module writes. There is no endpoint to write to: the gateway
 * opens the database `mode=ro`, and stage transitions belong to the harness.
 */

const DEFAULT_BASE = "http://127.0.0.1:8100";

export function gatewayBase(): string {
  // A deployment can move the gateway; the default is where `dume studio` puts
  // it. Read once per call rather than cached, so a settings change takes
  // effect without a restart.
  try {
    return localStorage.getItem("aethrionis.dume.gateway") || DEFAULT_BASE;
  } catch {
    return DEFAULT_BASE;
  }
}

export type WorkPackage = {
  wp_id: string;
  title: string;
  state: string;
  wave: number;
  candidate: string | null;
  producer: string | null;
  waiting_on: string[];
};

/**
 * The shapes below are the gateway's, checked against what it actually
 * returns. They were written from memory first and every field name was wrong;
 * the panel rendered `undefined` in every slot and showed an em dash, which
 * reads as "DUM-E recorded nothing" rather than "the client asked for the
 * wrong key". A blank that means two different things is worse than an error.
 */
export type Candidate = {
  /** The revision this evidence describes. */
  candidate: string;
  /** True when the package has moved on and this describes an earlier
   *  revision. */
  stale: boolean;
  current_candidate: string;
  worktree: string;
  files: string;
  tests: string;
  /** "RED exit=2, GREEN exit=0, 7 tool calls" — the test-first evidence. */
  discipline: string;
  verdict: string;
};

export type Review = {
  kind: string;
  verdict: string;
  reason: string;
  findings: number;
};

export type Verification = {
  candidate: string;
  exit: string;
  summary: string;
  fresh_checkout: boolean;
};

export type Evidence = {
  name: string;
  bytes: number;
  /** A zero-byte artefact is evidence of nothing, and says so. */
  empty: boolean;
  kind: string;
};

export type Transition = {
  at: string;
  from: string;
  to: string;
  actor: string;
  reason: string;
};

export type Gate = {
  verdict: string;
  evaluated_at: string;
  candidate_revision: string;
  checks: {
    name: string;
    /** What the check was asking. Carried so a passing gate can be read
     *  rather than trusted. */
    question: string;
    passed: boolean;
    detail: string;
  }[];
};

export type PackageDetail = {
  package: WorkPackage;
  candidate: Candidate | null;
  reviews: Review[];
  verification: Verification | null;
  gate: Gate | null;
  evidence: Evidence[];
  findings: { severity: string; summary: string }[];
  history: Transition[];
};

export type StateSummary = {
  current: WorkPackage | null;
  counts: Record<string, number>;
  runtimes: {
    runtime_id: string;
    model: string;
    family: string | null;
    status: string;
    mode: string;
    local: boolean;
    qualified: string[];
  }[];
  last_run: string | null;
};

/**
 * A failed read is an error, never an empty result.
 *
 * Returning `{findings: []}` when the gateway is down would render as "no
 * findings", which is a different claim from "we could not ask". The caller is
 * given the failure and shows it.
 */
async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${gatewayBase()}${path}`, {
    signal,
    headers: { accept: "application/json" },
  });
  const text = await response.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error(
      `DUM-E gateway returned ${response.status} and not JSON: ${text.slice(0, 200)}`,
    );
  }
  if (!response.ok) {
    const message =
      typeof body === "object" && body && "error" in body
        ? String((body as { error: unknown }).error)
        : `HTTP ${response.status}`;
    throw new Error(`DUM-E gateway: ${message}`);
  }
  return body as T;
}

export const dumeApi = {
  state: (signal?: AbortSignal) => get<StateSummary>("/api/state", signal),
  packages: (signal?: AbortSignal) =>
    get<{ packages: WorkPackage[] }>("/api/packages", signal),
  package: (wpId: string, signal?: AbortSignal) =>
    get<PackageDetail>(`/api/package?id=${encodeURIComponent(wpId)}`, signal),
  activity: (signal?: AbortSignal) =>
    get<{ activity: { at: string; wp_id: string; text: string }[] }>(
      "/api/activity",
      signal,
    ),
};

export type RelayConfig = {
  relay_ws: string;
  relay_http: string;
  invite: string | null;
  /** True when this deployment has a roster, so joining must be earned. */
  membership_required: boolean;
};

/**
 * Where AETHRIONIS's own relay is.
 *
 * Upstream's onboarding sends anyone without a community to a hosted service to
 * sign up for one. AETHRIONIS runs the relay, so there is nothing to sign up for,
 * and sending the operator to a third party for an account they do not need is
 * a worse first run as well as a wider trust boundary than the work requires.
 */
export async function relayConfig(
  signal?: AbortSignal,
): Promise<RelayConfig> {
  return get<RelayConfig>("/api/relay", signal);
}

/** The invite deep link, split into the two things the join flow wants. */
export function parseInvite(
  invite: string | null,
): { relayUrl: string; code: string } | null {
  if (!invite) return null;
  try {
    const url = new URL(invite);
    const relayUrl = url.searchParams.get("relay");
    const code = url.searchParams.get("code");
    return relayUrl && code ? { relayUrl, code } : null;
  } catch {
    return null;
  }
}

// ---- membership ------------------------------------------------------------
//
// Identity, membership and admission are three things, kept apart. The identity
// is the key this machine holds. The membership is a GitHub account in this
// deployment's roster — the part a person can be added to and removed from. The
// admission is a relay invite, minted only once the two are bound.
//
// The GitHub token never comes here. The gateway uses it to read one login and
// drops it; what returns is the login and a verdict.

export type DeviceCode = {
  device_code: string;
  user_code: string;
  verification_uri: string;
  interval: number;
  expires_in: number;
};

export type MembershipVerdict =
  | { status: "pending" }
  | {
      status: "admitted";
      login: string;
      via?: string;
      relay_ws: string;
      invite: string | null;
    }
  | { status: "refused"; login: string; reason: string };

async function post<T>(path: string, body: Record<string, string> = {}): Promise<T> {
  const response = await fetch(`${gatewayBase()}${path}`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body).toString(),
  });
  const text = await response.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`the gateway returned ${response.status}: ${text.slice(0, 200)}`);
  }
  if (!response.ok && response.status !== 403) {
    const message =
      typeof parsed === "object" && parsed && "error" in parsed
        ? String((parsed as { error: unknown }).error)
        : `HTTP ${response.status}`;
    const error = new Error(message) as Error & { unconfigured?: boolean };
    if (
      typeof parsed === "object" &&
      parsed &&
      (parsed as { unconfigured?: boolean }).unconfigured
    ) {
      // A deployment that has not registered an OAuth app yet is a different
      // situation from one that refused this person, and the caller says so.
      error.unconfigured = true;
    }
    throw error;
  }
  return parsed as T;
}

export const membership = {
  begin: () => post<DeviceCode>("/api/membership/begin"),
  poll: (deviceCode: string) =>
    post<MembershipVerdict>("/api/membership/poll", { device_code: deviceCode }),
};

export type Roster = {
  configured: boolean;
  reason?: string;
  client_id?: string;
  logins: string[];
  org: string | null;
  /** Whether opening the application asks for a GitHub account. */
  require: boolean;
  pending: {
    login: string;
    state: string;
    first_asked: string;
    last_asked: string;
  }[];
};

export const roster = {
  read: () => post<Roster>("/api/membership/roster"),
  decide: (login: string, verdict: "approve" | "deny") =>
    post<{ login: string; state: string }>("/api/membership/decide", {
      login,
      verdict,
    }),
  configure: (clientId: string, org: string, require: boolean) =>
    post<{ status: string }>("/api/membership/configure", {
      client_id: clientId,
      org,
      require: require ? "1" : "0",
    }),
};

// ---- commanding DUM-E ------------------------------------------------------
//
// The same gateway the console and Telegram use. The interface gets no
// privilege they do not have: a DANGEROUS_ACTION still asks for confirmation,
// an invented verb is still refused, and every command lands in the same audit
// trail. There is one vocabulary because a second copy of it is a second thing
// that can be wrong about who may do what.

export type CommandResult =
  | { outcome: "EXECUTED"; action: string; class: string; audit: string; reply: string }
  | { outcome: "AWAITING_CONFIRMATION"; action: string; confirmation_ref: string; reply: string }
  | { outcome: "REFUSED"; reply: string }
  | { outcome: "ERROR"; reply: string };

export type Vocabulary = {
  command: string;
  class: string;
  summary: string;
  parameters: string[];
  needs_confirmation: boolean;
}[];

export const dume = {
  run: (text: string) => post<CommandResult>("/api/command", { text }),
  confirm: (ref: string) => post<CommandResult>("/api/command", { confirm: ref }),
  vocabulary: () => get<{ commands: Vocabulary }>("/api/vocabulary"),
};
