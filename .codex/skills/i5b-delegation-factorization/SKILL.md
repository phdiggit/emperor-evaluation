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

Judge the concrete result of the authorization arrangement proven by this material. Do not use overall fame, later biography, generic victory language, later rebellion, alleged treason, self-protection troop gathering, suspicion, demotion, execution, purge, or failure to preserve talent as `delegation` result feedback unless the quote proves those events are the direct execution result of the authorization itself.

- `重大成功强烈体现授权合理` requires a clear authorization chain plus decisive, large-scale, or structurally important success that strongly validates role fit.
- `正常成功或职责履行良好` fits ordinary victory, competent execution, stable duty performance, or continued use with concrete task feedback.
- `履职反馈较弱` fits title or appointment facts, weak performance evidence, partial context, or success that is not clearly tied to the authorization.
- `授权后任务结果较差` fits bounded task failure, poor execution, or limited loss caused by the authorization chain.
- `授权直接造成重大军政失败、治理损害或关键职责失守` requires a wrong person, wrong post, or wrong authority arrangement that directly causes major military, administrative, fiscal, institutional, or frontier damage.
- `错误授权直接造成连续性、结构性或大规模后续损害` requires broad, sustained, or systemic damage caused by the authorization chain. Do not use this for a single defeat, later scandal, purge, demotion, or failure to preserve talent unless the authorization itself directly produced that damage.

Side/value guard: positive rows must not choose negative-valued `result_feedback`; negative rows must not choose positive-valued `result_feedback`.

## Common Traps

- Do not turn a bare appointment into positive `result_feedback=正常成功`.
- Do not turn an ordinary campaign win into `重大成功` unless it changes the larger situation.
- Do not score posthumous slander, merit protection, political cruelty, later rebellion, alleged treason, self-protection troop gathering, suspicion, demotion, execution, purge, or failure to preserve talent as delegation result feedback unless the quote proves an authorization-result chain.
- If a later rebellion or troop gathering is explained by fear after peer meritorious officials were killed, court suspicion, political insecurity, or self-preservation, use `supporting_only` or `exclude` for delegation; route it to neighboring-rule review.
- Do not treat revocation or emperor correction of a delegate as negative `result_feedback` unless it is the direct result of the authorization arrangement being assessed.

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
