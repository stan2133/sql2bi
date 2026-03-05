# Domain Pack: Fraud And Risk

## Scope
Use for payment fraud, account abuse, promo abuse, identity risk, chargeback diagnostics, and risk policy evaluation.

## Core Metrics
- `fraud_rate`: confirmed fraud transactions / total transactions.
- `chargeback_rate`: chargeback transactions / settled transactions.
- `false_positive_rate`: good transactions blocked / total blocked transactions.
- `rule_precision`: fraud caught by rule / all transactions flagged by rule.
- `rule_recall`: fraud caught by rule / total confirmed fraud.
- `manual_review_hit_rate`: fraud found in manual review / manual review volume.
- `loss_rate`: fraud loss amount / gross payment volume.

## Metric Semantics Guardrails
- Separate `attempted`, `authorized`, and `captured` transaction states.
- Define fraud label maturity window (for example 45 to 90 days).
- Distinguish first-party abuse vs third-party payment fraud.
- Keep cost components explicit: direct loss, operational cost, customer friction cost.

## Hypothesis Tree Seeds
- Chargeback spike:
  - risky channel or merchant mix shift
  - weaker device fingerprint coverage
  - delayed model/rule update
- False positives increase:
  - threshold too strict
  - model drift from seasonality
  - data feed gaps in risk signals
- Fraud loss increase with stable rate:
  - higher average ticket size attacked
  - high-value segments under-protected

## Typical Dimensions
- `payment_method`, `card_bin`, `issuer_country`
- `merchant`, `channel`, `campaign`
- `device_id`, `ip_country`, `email_domain`
- `risk_score_bucket`, `review_outcome`

## Audit And Governance Checks
- Verify label leakage is not present in feature set.
- Check policy changes effective dates align with analysis window.
- Validate dispute lifecycle timestamps (transaction, dispute, resolution).
- Reconcile blocked amount vs approved amount after rule changes.
- Track both fraud capture and customer conversion impact.

## Reporting Rules
- Report risk metrics with dual objective:
  - protect good user conversion
  - reduce fraud loss
- Include trade-off curve when threshold decisions are involved.
- Avoid single-metric optimization claims.

## Action Playbook
- High chargeback + low false positive:
  - tighten rules in high-risk segments first
  - add adaptive velocity checks
- High false positive + stable fraud:
  - relax thresholds in low-risk cohorts
  - prioritize model recalibration
- Promo abuse concentrated by referral clusters:
  - apply graph-based link analysis and referral velocity controls

## Common Questions
- Which rules cause the largest false-positive cost?
- Where are chargebacks concentrated by BIN/country/channel?
- Did the latest risk policy change improve net risk-adjusted margin?
