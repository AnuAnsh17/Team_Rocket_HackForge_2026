import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function AllowancePage() {
  return (
    <>
      <PageHeader
        title="My allowance"
        description="The limits that apply to you, and where they come from."
      />

      <PlaceholderNotice
        title="No allowance is configured"
        whatIsMissing={
          "No approved policy document has been supplied, so there are no limits to show. " +
          "This is deliberate: an invented limit would be indistinguishable from a real one, " +
          "and you would make decisions based on it. An allowance amount cannot even be " +
          "stored without a cited policy clause."
        }
        blockedOn="The company policy document, with clause references."
      />

      <Card title="What will be shown here" description="And where each number comes from.">
        <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
          <li>
            <span className="text-[var(--color-text)]">Your applicable limits</span> — from
            the policy assigned to you, resolved from your current role, grade and location
            rather than guessed.
          </li>
          <li>
            <span className="text-[var(--color-text)]">The clause behind each limit</span> —
            the section of the policy it comes from, so you can check it yourself.
          </li>
          <li>
            <span className="text-[var(--color-text)]">Your usage this period</span> —
            counted only over the claims the policy says count.
          </li>
        </ul>
        <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
          Different people have different limits, and the design does not assume that a more
          senior role means a larger allowance. That is a policy decision, and it will be
          shown as the policy states it.
        </p>
      </Card>
    </>
  );
}
