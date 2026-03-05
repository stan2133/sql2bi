# Domain Pack: Growth Hacking

## Scope
Use for acquisition, activation, retention, referral, monetization, and experiment analysis.

## Core Metrics
- `new_users`: distinct new users in period.
- `activation_rate`: `activated_users / new_users`.
- `d1_retention`: users active on day 1 after signup / signup cohort users.
- `d7_retention`: users active on day 7 after signup / signup cohort users.
- `paid_conversion_rate`: `paid_users / active_users`.
- `ltv`: cumulative contribution margin per acquired user over window.
- `cac`: acquisition spend / acquired customers.
- `ltv_cac_ratio`: `ltv / cac`.

## Metric Semantics Guardrails
- Define cohort anchor (`signup_date`, `first_purchase_date`, or first key action).
- Separate user-level and session-level conversion.
- Enforce attribution model (last click, first touch, MMM-derived).
- Keep exclusion rules explicit (internal/test users, bots, refunds).

## Hypothesis Tree Seeds
- Acquisition drop:
  - channel spend cut
  - auction price inflation
  - landing page degradation
- Activation drop:
  - onboarding friction increase
  - app performance regression
  - weaker channel mix
- Retention drop:
  - feature quality regression
  - poor first-week value realization
  - support friction increase
- Monetization drop:
  - discount mix shift
  - low intent traffic growth
  - checkout friction

## Typical Dimensions
- `channel`, `campaign`, `adset`
- `country`, `region`, `language`
- `device_type`, `os`, `app_version`
- `cohort_week`, `signup_source`

## Experiment Analysis Rules
- Always define control/treatment assignment method.
- Check sample ratio mismatch before effect estimation.
- Report absolute lift and relative lift.
- Show confidence interval or p-value if available.
- Avoid declaring winner when effect size is unstable across key segments.

## Data Quality And Audit Checks
- Verify event deduplication keys (`event_id`, `user_id`, `event_time`).
- Check late-arriving events impact on recent cohorts.
- Reconcile user counts across funnel steps.
- Validate spend table timezone and currency normalization.

## Action Playbook
- If `activation_rate` drops and onboarding completion falls:
  - prioritize onboarding funnel fixes
  - run friction-focused experiment
- If `retention` drops with stable acquisition:
  - inspect first-week product usage and support tickets
  - segment by first value moment completion
- If `ltv_cac_ratio` falls:
  - reduce low-quality channel spend
  - rebalance to channels with stronger payback

## Common Questions
- Which channels drive low-CAC high-retention users?
- Why did D7 retention drop last month?
- Which onboarding step causes the largest conversion loss?
