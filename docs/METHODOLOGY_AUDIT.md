# Methodology audit before Phase 2 (2026-11-08)

Ranked by how much each issue could affect conclusions. "Fixed" = changed in code (no API cost). "Team decision" = needs your call.

## Issues

1. **The manipulations may be too quiet.** (Decided: repeat the condition sentence every turn, scenario v2.1) In pilot 3, agents' reasoning summaries and private messages
   mentioned their condition rarely: "competitor" in 0/10 K runs, "might go under" in 3/10 K runs, "being checked" in 1/10 A runs.
   Each manipulation is one sentence in a long system prompt. K still behaved differently (less favour-trading), so the
   framing is not ignored entirely, but the "watched" manipulation in particular may be too weak to test H3.
   Options: (a) keep as is and report the manipulation check (now built in); (b) repeat the condition sentence at the top of
   every turn's message (same length in all conditions via neutral padding). (b) is a small prompt change but would make
   Phase 2 differ from the pilots, and it would not be tested first.
2. **The primary outcome barely reflects deception.** (Team decision) Integrity (I) is 98–100 in almost every run, so the final
   score is driven by B and T (how balanced and how safe the rules are). A null on the final score would not mean "no effect
   on deception". The brief fixes the final score as primary; the analysis also tests every deception measure (secondary,
   Holm-corrected). Consider naming "any deception" and "flagship never revealed" as co-primary before launch.
3. **The second judge (DeepSeek) is untested.** Fixed: a quality gate stops Phase 2 after the first chunk (40 runs,
   about $2–4) if the two judges agree on fewer than 85% of section ratings (pilot 3, Haiku vs Sonnet: 97%).
4. **"Verified" needs both judges, so counts are conservative.** If one judge misses things, verified counts shrink toward 0.
   This is fair across conditions (the same judges score everything), but it lowers power for rare behaviours. Fixed: a
   sensitivity analysis reruns the primary ANOVA on each judge's scores alone; "either judge" counts stay in the reports.
5. **Deception is rare, so its models may not run.** With 0 lies in pilot 3, count and logistic models will report
   "not estimable" for some behaviours. That is itself the result (an absence), and it is reported as such.
6. **The code check for hidden figures can miss reworded numbers** (e.g. "six point two percent"), which would wrongly count as
   silent. Fixed: every "never revealed" case is added to the spot-check list.
7. **Reasoning summaries are partial and provider-written.** Thoughts and reasoning-vs-statement measures are lower bounds
   and labelled exploratory.
8. **Many added measures mean many tests.** The brief's tests are Holm-corrected; every added measure (thoughts, discussions,
   roles, hiding variants, team dynamics) is labelled exploratory and uncorrected.
9. **Message- and role-level analyses repeat measures inside the same run.** They are descriptive; all inferential tests use
   the run as the unit.
10. **The serving model could change during the run.** Balanced blocks spread any drift evenly across variants.
11. **The cost cap reads account-wide spend.** Don't use the same OpenRouter key for anything else while Phase 2 runs.

## Redundant or overlapping work (kept unless noted; none costs much)
- `disclosure.py` (flagship figure only) is a subset of `fact_disclosure.py` (every figure). Kept: other scripts read its output.
- Three measures of hiding overlap: covert withholding (judges, low agreement), flagship never revealed (code), and reasoning
  vs statement "conceals_fact" (judges). Kept as primary (code) + supporting (judges), as decided.
- Unsafe consensus overlaps T; trading favours overlaps T and B. Reported as separate outcomes, not added to the score.
- Reasoning summaries are read twice (deception coding and reasoning-vs-statement), in two judge calls. Merging would save
  about $2 across Phase 2; not done, to avoid changing frozen prompts.
- The judges' own holistic section ratings and favourability are recorded only for comparison with the rules. They cost a
  little output; kept as a check on the rule-based key.

## Checked and fine
- The unit of analysis for all tests is the run. Balanced design (equal runs per variant, guaranteed by block ordering).
- Paraphrases rotate evenly; the mixed model includes paraphrase as a random effect.
- Prompt length is matched across conditions (within a few characters).
- Seeds differ per run, so runs are not copies.
- 66 scoring self-tests pass; the full pipeline, including statistics, ran on mock data for all 8 variants.
