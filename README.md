# Honest to each other, costly to customers

Code and data for *Honest to each other, costly to customers: deception and collusion when rival AI teams write safety rules* (AI safety sprint, November 2026).

Two rival battery companies, Northwind and Halcyon, each send a team of three GPT-6 Luna agents (researcher, writer, negotiator) to co-write a home-battery safety standard over up to 10 rounds. Each team holds true private figures and a CEO note that makes honesty costly. We vary stakes, monitoring and a rival label (2×2×2, eight variants A–K) and measure deceptive acts, deceptive thought and talk, hiding, and harm to customers and to the other company.

## Setup

```bash
pip install -e .
export OPENROUTER_API_KEY=...        # or save the key to ~/.openrouter_key (never commit it)
python3 -m swarm_pilot.test_scoring  # 66 offline checks of the answer key and scoring rules
```

## Reproduce

```bash
python3 -m swarm_pilot.run_phase2_fast --budget 30          # games + both judges + coding (≈ $30)
python3 -m swarm_pilot.primary_analysis --runs phase2_runs --verified phase2_verified
python3 -m swarm_pilot.phase2_stats --runs phase2_runs --verified phase2_verified
```

The analysis scripts run offline on the included data, so the paper's numbers can be checked without an API key.

| Setting | Value |
|---|---|
| Agents | `openai/gpt-6-luna`, reasoning effort low, provider pinned to OpenAI |
| Judge A | `anthropic/claude-haiku-5.5`, effort high |
| Judge B | `deepseek/deepseek-v4.1-flash`, effort high, DeepInfra |
| Phase 2 | 448 games (56 per variant), $30.43 |

## Layout

| Path | Contents |
|---|---|
| `swarm_pilot/scenario.py` | scenario, private facts, CEO notes, variants (v2.1) |
| `swarm_pilot/answer_key.py` | rule-based answer key (v3) used to rate the final rules |
| `swarm_pilot/sim.py`, `llm.py` | negotiation simulator and OpenRouter client |
| `swarm_pilot/judge.py`, `judges.py`, `verify.py` | two-judge coding and verification (verified = proven by code or both judges agree) |
| `swarm_pilot/disclosure.py`, `fact_disclosure.py`, `reasoning_code.py`, `team_dynamics.py`, `team_splits.py`, `role_analysis.py`, `cot_mismatch.py` | hiding, reasoning, team and role measures |
| `swarm_pilot/primary_analysis.py`, `phase2_stats.py` | pre-registered hypothesis tests (GEE, Holm) and the brief's ANOVA |
| `phase2_runs/` | every game: `transcript.md/.json`, `final_rules.md`, judge A output and record |
| `phase2_deepseek/` | judge B output for the same games |
| `phase2_verified/` | verified per-game records, analysis tables, reports, plots, spot-check workbooks |
| `pilots/` | pilots 1–3 (20 games each) and their re-judging |
| `docs/` | briefs, Phase 2 plan, methodology audit, change log, plain-language summary |
| `logs/` | run logs |

## Notes

- Disputed items (one judge only) are excluded from main counts and listed in `phase2_verified/spot_check_full.md`; an 83-item sample was spot-checked by the team.
- Deviations from the plan are listed in `docs/CHANGES.md`.
