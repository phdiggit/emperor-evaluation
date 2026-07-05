---
name: i5b-delegation-factorization
description: Narrow calibration for emperor-evaluation I5B delegation factorization. Use only when explicitly requested for rule_code=delegation authorization_intensity/result_feedback review; do not use for routine bulk factorization that already receives package side and finite factor labels.
---

# I5B Delegation Factorization

## Overview

Use this skill only for targeted I5B `delegation` factorization review. It narrows two factors: `authorization_intensity` and `result_feedback`.

Do not use it for routine bulk factorization, final scoring, database writes, schema design, source fetching, object identity, talent grade assignment, side review, or other I5B rules.

Treat package `direction` / `side` as fixed input. Do not rejudge positive/negative.

## Decision Order

For each material, decide in this order:

1. Decide whether the material is really `delegation`.
2. Choose `score`, `supporting_only`, or `exclude`.
3. Use the given side.
4. Assign `authorization_intensity` from the authority granted.
5. Assign `result_feedback` from concrete feedback in this material.

## Delegation Boundary

Score only concrete appointment, entrustment, authority allocation, military/civil delegation, role fit, and task feedback.

Use `supporting_only` when the material proves title, background, context, reputation, or later consequence but does not itself show an assessable authorization-result chain.

Use `exclude` when the material belongs mainly to another rule.

## Authorization Intensity

Judge scope and authority. Do not upgrade because the task later succeeded.

- `国家级、危局或长期关键授权` only when the emperor grants national, central, whole-theater, crisis, long-running, or cross-military-civil authority.
- `重大军政事务授权` for important campaigns, regional governance, major civil office, important military command, or substantial but bounded responsibility.
- `单一领域的真实授权` for one mission, one negotiation, one limited military task, one office with ordinary scope, or one local assignment.
- `名义授权或职责不清` when title exists but power, task, or responsibility is vague.

High office alone is not enough for the highest intensity. A successful battle alone is not enough either.

## Result Feedback

Judge feedback proven by this material. Do not use overall fame, later biography, or generic victory language.

- `重大成功强烈体现授权合理` requires a clear authorization chain plus decisive, large-scale, or structurally important success that strongly validates role fit.
- `正常成功或职责履行良好` fits ordinary victory, competent execution, stable duty performance, or continued use with concrete task feedback.
- `履职反馈较弱` fits title or appointment facts, weak performance evidence, partial context, or success that is not clearly tied to the authorization.
- `效果较差` fits bounded failure or weak task result without major structural damage.
- `重大错授、长期错用或对人才结构造成明显损害` requires wrong person or wrong post with serious harm to governance, military order, or talent structure.
- `关键战机撤权、撤授权或权责反转` requires the emperor's authorization behavior itself to break task responsibility or block core talent use. Correcting a delegate's mistake is not automatically negative.
- `连续性人才安全灾难、关键团队崩坏或大规模后续损害` requires broad, sustained, or structural damage. Do not use this for a single defeat or a later scandal unless the authorization chain itself caused the damage.

Side/value guard: positive rows must not choose negative-valued `result_feedback`; negative rows must not choose positive-valued `result_feedback`.

## Common Traps

- Do not turn a bare appointment into positive `result_feedback=正常成功`.
- Do not turn an ordinary campaign win into `重大成功` unless it changes the larger situation.
- Do not score posthumous slander, merit protection, or political cruelty as delegation unless it directly changes an authorization relationship.
- Do not treat emperor correction of a delegate as negative unless it destroys authority or talent use.

## Quick Calibration

- A central minister entrusted with high state affairs can justify highest authorization intensity, but if the row only proves appointment or title, feedback should be weak or supporting.
- A single successful mission or one-city surrender usually does not justify strongest positive feedback.

## Final Self-Check

Before writing a patch row, check:

1. Would this label still look right if the emperor and famous object names were hidden?
2. Is `authorization_intensity` based only on granted authority?
3. Is `result_feedback` based only on concrete feedback in this material?
4. Does the `result_feedback` value sign match the given side?
5. Is this really delegation rather than a neighboring rule?
