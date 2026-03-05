# Domain Pack: NPS And Customer Experience

## Scope
Use for NPS, CSAT, support quality, complaint analysis, and churn-risk diagnostics driven by customer sentiment.

## Core Metrics
- `nps`: `%promoters - %detractors`.
- `promoter_rate`: promoters / valid responses.
- `detractor_rate`: detractors / valid responses.
- `response_rate`: survey responses / invitations.
- `csat`: satisfied responses / valid responses.
- `first_response_time`: median minutes to first support response.
- `resolution_time`: median time from ticket open to close.
- `contact_rate`: support contacts / active users.
- `complaint_rate`: complaints / orders or active users.

## Metric Semantics Guardrails
- Define NPS scoring bands explicitly (usually 0-6 detractor, 7-8 passive, 9-10 promoter).
- Exclude invalid responses and duplicate survey submissions.
- Separate product NPS vs service NPS when both exist.
- Control for response bias by segment and response channel.

## Hypothesis Tree Seeds
- NPS drop:
  - delivery/service incident
  - product quality regression
  - support backlog increase
  - expectation mismatch due to campaign messaging
- CSAT drop with stable NPS:
  - operational issue with support handling
  - delay in resolution or escalation quality
- Churn rise with detractor spike:
  - unresolved high-severity issues in key cohorts

## Typical Dimensions
- `product_line`, `service_type`
- `region`, `market`, `language`
- `ticket_category`, `severity`, `channel`
- `customer_tenure`, `plan_tier`, `account_segment`

## Audit Checks
- Verify response sample size per segment before ranking.
- Check survey timing consistency relative to user journey events.
- Reconcile ticket events with CRM/support system source of truth.
- Flag low response-rate segments as low confidence.

## Reporting Rules
- Always report NPS with `response_rate` and sample size.
- Do not over-interpret small-sample movements.
- Tie sentiment changes to operational metrics (FRT, resolution time, reopen rate).
- Separate what users said from inferred causes.

## Action Playbook
- Detractor surge in one segment:
  - review top complaint themes
  - route focused remediation owner
- High contact rate + longer resolution time:
  - add triage capacity and automate repetitive issue handling
- NPS recovery with flat CSAT:
  - validate sustained trend before claiming quality turnaround

## Common Questions
- What drove the NPS drop this quarter?
- Which complaint themes correlate most with churn?
- Is support speed or resolution quality the main driver of detractors?
