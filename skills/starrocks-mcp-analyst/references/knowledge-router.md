# Knowledge Router For Step 2

## Purpose
Map user intent to the right business knowledge packs.
Load only the minimum required domain files to avoid context bloat.

## Routing Rule
1. Extract intent tags from decision card and user ask.
2. Match tags to primary domain and optional secondary domain.
3. Load primary first, then secondary only when needed.
4. Record selected files in `loaded_knowledge_files`.

## Tag To Domain Map
- Growth and experiment tags:
  - tags: `growth`, `acquisition`, `activation`, `retention`, `referral`, `experiment`, `a/b`, `funnel`
  - load: `references/domains/growth-hacking.md`
- Risk and abuse tags:
  - tags: `fraud`, `chargeback`, `abuse`, `risk`, `aml`, `kyc`, `suspicious`
  - load: `references/domains/fraud-risk.md`
- Customer sentiment tags:
  - tags: `nps`, `csat`, `complaint`, `support`, `churn_reason`, `cx`
  - load: `references/domains/nps-cx.md`
- Sales execution tags:
  - tags: `sales`, `pipeline`, `opportunity`, `win_rate`, `quota`, `forecast`, `crm`
  - load: `references/domains/sales-ops.md`
- Manufacturing tags:
  - tags: `manufacture`, `manufacturing`, `oee`, `yield`, `scrap`, `downtime`, `line`, `work_order`, `factory`
  - load: `references/domains/manufacturing-ops.md`
- Supply chain tags:
  - tags: `inventory`, `otif`, `fill_rate`, `lead_time`, `stockout`, `procurement`, `logistics`
  - load: `references/domains/supply-chain.md`
- Finance and reporting tags:
  - tags: `margin`, `ebitda`, `cashflow`, `dso`, `dpo`, `dio`, `budget`, `variance`, `corporate_finance`, `cooperate_finance`
  - load: `references/domains/corporate-finance.md`
- HR and people operations tags:
  - tags: `hr`, `people`, `headcount`, `hiring`, `attrition`, `turnover`, `retention`, `recruiting`, `talent`, `performance_review`, `absence`
  - load: `references/domains/hr-people-ops.md`

## Multi-Domain Combinations
- Growth + NPS:
  - Use when conversion or retention drops with sentiment signals.
- Sales + Finance:
  - Use when pipeline looks strong but recognized revenue or margin underperforms.
- Manufacturing + Supply Chain:
  - Use when service level issues may come from both plant throughput and inbound supply.
- Fraud + Finance:
  - Use when short-term revenue grows with rising chargebacks or fraud losses.
- Sales + HR:
  - Use when quota attainment or productivity changes may be driven by staffing, tenure, or ramp dynamics.

## Ambiguity Resolution
- `retention` with `user`, `cohort`, `activation`, `conversion`:
  - prioritize `references/domains/growth-hacking.md`
- `retention` with `employee`, `attrition`, `headcount`, `hiring`:
  - prioritize `references/domains/hr-people-ops.md`

## Conflict Handling
- If definitions differ across domains:
  - prioritize governance and finance definitions
  - keep secondary-domain metric as supplemental view
  - disclose conflict in `semantic_risks`

## Minimum Coverage Rule
Before leaving Step 2, confirm:
1. one primary domain loaded
2. metric formula resolved or marked provisional
3. domain-specific risk checks identified
