import { Card, PageHeader, PlaceholderNotice } from "@/components/ui";

export default function PolicyRegistryPage() {
  return (
    <>
      <PageHeader
        title="Policy registry"
        description="Approved policy versions, the rule clauses the engine uses, and their effective assignments."
      />

      <PlaceholderNotice
        title="No policy version is loaded, and none can be"
        whatIsMissing={
          "No authoritative policy document has been supplied, so the registry holds zero " +
          "rules and every claim evaluates to UNKNOWN. This is the correct behaviour, not " +
          "a defect: an invented rule that approves or rejects real claims is worse than " +
          "no rule."
        }
        blockedOn="The company policy document, with clause references."
      />

      <Card
        title="What the database refuses to store"
        description="Two constraints make an invented rule impossible, not merely discouraged."
      >
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="font-mono text-xs text-[var(--color-text)]">
              ck_policy_rules_source_requires_validation
            </dt>
            <dd className="text-[var(--color-text-muted)]">
              A rule may be active only when it carries a source clause, a named validator,
              a validation timestamp and an evaluator type.
            </dd>
          </div>
          <div>
            <dt className="font-mono text-xs text-[var(--color-text)]">
              ck_allowance_profile_items_limit_requires_source
            </dt>
            <dd className="text-[var(--color-text-muted)]">
              An allowance amount may be stored only alongside a cited clause and a
              currency.
            </dd>
          </div>
        </dl>
      </Card>

      <Card
        title="Precedence is configuration, not specificity"
        description="Why the resolver reports a conflict instead of choosing."
      >
        <p className="max-w-prose text-sm text-[var(--color-text-muted)]">
          When two approved assignments at equal priority point at different policy
          versions, resolution returns <em>unresolved</em> with a reason rather than picking
          one. &ldquo;The most specific scope wins&rdquo; and &ldquo;a higher grade means a
          higher allowance&rdquo; are both policy semantics, and assuming either would
          silently change who gets reimbursed. See{" "}
          <span className="font-mono text-xs">docs/role-policy-hierarchy.md</span>.
        </p>
      </Card>
    </>
  );
}
