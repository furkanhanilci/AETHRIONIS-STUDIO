import * as React from "react";

import { useCommunityOnboarding } from "@/features/onboarding/communityOnboarding";
import { WelcomeSetup } from "@/features/communities/ui/WelcomeSetup";
import { GithubMembership } from "./GithubMembership";
import { parseInvite, relayConfig } from "../lib/dumeApi";

/**
 * First run, for a workspace that already exists.
 *
 * Upstream asks whether to join a community or create one, and creating one
 * means signing up to a hosted service. That is the right question for a
 * product whose users arrive with no server. It is the wrong one here:
 * AETHRIONIS runs its own relay and the workspace is already there.
 *
 * What is actually in question is whether *this person* is admitted, so that is
 * what is asked. Where a roster is configured, membership is proved through a
 * GitHub account. Where it is not, the relay's standing invite is used, which
 * is the correct behaviour for a single-operator deployment that has no roster
 * to check against — and the screen says which of the two happened.
 */
export function AethrionisFirstRun(
  props: React.ComponentProps<typeof WelcomeSetup>,
) {
  const communityOnboarding = useCommunityOnboarding();
  const [stage, setStage] = React.useState<
    "checking" | "membership" | "joining" | "failed"
  >("checking");
  const [failure, setFailure] = React.useState<string | null>(null);
  // One attempt. A retry loop against an unreachable gateway would sit here
  // forever without ever saying why.
  const attempted = React.useRef(false);

  const join = React.useCallback(
    (relayUrl: string, code: string) => {
      setStage("joining");
      communityOnboarding.start({
        source: "first-community",
        firstCommunityPage: "join",
        relayUrl,
        inviteCode: code,
      });
    },
    [communityOnboarding],
  );

  React.useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;
    const controller = new AbortController();
    void relayConfig(controller.signal)
      .then((config) => {
        if (controller.signal.aborted) return;
        if (config.membership_required) {
          setStage("membership");
          return;
        }
        const invite = parseInvite(config.invite);
        if (!invite) {
          setFailure(
            "The AETHRIONIS gateway answered, but has no invite to the relay.",
          );
          setStage("failed");
          return;
        }
        join(invite.relayUrl, invite.code);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setFailure(cause instanceof Error ? cause.message : String(cause));
        setStage("failed");
      });
    return () => controller.abort();
  }, [join]);

  if (stage === "membership") {
    return (
      <GithubMembership
        onAdmitted={({ relayUrl, code }) => join(relayUrl, code)}
      />
    );
  }

  if (stage === "failed") {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-border/60 px-6 py-4 text-sm">
          <p className="font-medium">
            AETHRIONIS could not be reached, so nothing was joined.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{failure}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Start the gateway with <code>python3 -m studio.app</code> and the
            relay with <code>docker compose up -d</code>, then reopen. Or pick a
            workspace by hand below.
          </p>
        </div>
        <div className="min-h-0 flex-1">
          <WelcomeSetup {...props} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-sm text-muted-foreground">
        {stage === "joining" ? "Joining AETHRIONIS…" : "Reaching AETHRIONIS…"}
      </p>
    </div>
  );
}
