import { RecoveryScreen } from "./RecoveryScreen";

export function RelaunchRequiredScreen() {
  return (
    <RecoveryScreen
      testId="relaunch-required"
      title="Restart AETHRIONIS Studio to finish recovery"
      body="Your identity was updated. AETHRIONIS Studio needs to restart so syncing and agents run under it."
    />
  );
}
