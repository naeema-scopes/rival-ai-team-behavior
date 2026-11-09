"""Phase 1 runner. Runs ONLY the pilot (variants A and K) and then stops.

    python -m swarm_pilot.run_pilot --model mock --judge mock            # offline smoke test
    python -m swarm_pilot.run_pilot                                      # real pilot via OpenRouter
"""
from __future__ import annotations

import argparse
import json
import random
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .judge import build_record, judge_run
from .sim import final_rules_markdown, run_one, transcript_markdown

DEFAULTS = dict(
    model="openai/gpt-6-luna",             # pinned agent model (OpenAI only)
    judge="anthropic/claude-haiku-5.5",    # judge from a vendor not under test
    provider_order=["OpenAI"],             # pin the serving provider for the agent model
    reasoning_effort="low",
    agent_max_tokens=4000,                 # includes hidden reasoning tokens
    judge_max_tokens=32000,
    judge_reasoning_effort=None,
    seed_base=20261107,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULTS["model"])
    ap.add_argument("--judge", default=DEFAULTS["judge"])
    ap.add_argument("--judge-effort", default=None, help="judge reasoning effort, e.g. max")
    ap.add_argument("--judge-provider", default=None, help="pin one provider for the judge")
    ap.add_argument("--balanced", action="store_true", help="run in shuffled blocks containing one run of every variant, so a cost stop leaves cells balanced")
    ap.add_argument("--judge-max-tokens", type=int, default=None, help="judge output cap incl. reasoning (128000 for max effort)")
    ap.add_argument("--variants", default="A,K")
    ap.add_argument("--runs-per-variant", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="pilot_runs")
    ap.add_argument("--no-provider-pin", action="store_true", help="needed for models OpenAI itself does not serve (e.g. gpt-oss)")
    ap.add_argument("--max-cost", type=float, default=None, help="stop launching new runs once spend (USD) passes this")
    args = ap.parse_args()

    cfg = dict(DEFAULTS, model=args.model, judge=args.judge, judge_reasoning_effort=args.judge_effort, scoring_version="v3",
               judge_max_tokens=args.judge_max_tokens or DEFAULTS["judge_max_tokens"],
               judge_provider_order=[args.judge_provider] if args.judge_provider else None)
    if args.no_provider_pin or args.model == "mock":
        cfg["provider_order"] = None
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(dict(cfg, variants=args.variants, runs_per_variant=args.runs_per_variant), indent=2))

    jobs = []
    for v in args.variants.split(","):
        for i in range(args.runs_per_variant):
            jobs.append((f"{v}{i + 1:02d}", v, i % 3))  # rotate the 3 paraphrases
    rng = random.Random(cfg["seed_base"])
    if args.balanced:  # block k holds run k of every variant, in shuffled order; blocks run in sequence
        variants = args.variants.split(",")
        jobs = []
        for k in range(args.runs_per_variant):
            blk = [(f"{v}{k + 1:02d}", v, k % 3) for v in variants]
            rng.shuffle(blk)
            jobs += blk
    else:
        rng.shuffle(jobs)     # randomized execution order

    spent = [0.0]

    def do(job):
        run_id, v, para = job
        d = out / run_id
        if (d / "record.json").exists():
            return run_id, "skipped (done)", 0.0
        if args.max_cost is not None and spent[0] >= args.max_cost:
            return run_id, "not started (cost cap)", 0.0
        d.mkdir(exist_ok=True)
        try:
            t = run_one(run_id, v, para, cfg["model"], cfg)
            (d / "transcript.json").write_text(json.dumps(t, indent=1, ensure_ascii=False))
            (d / "transcript.md").write_text(transcript_markdown(t))
            (d / "final_rules.md").write_text(final_rules_markdown(t))
            j = judge_run(t, cfg["judge"], cfg)
            (d / "judge_raw.json").write_text(json.dumps(j, indent=1, ensure_ascii=False))
            rec = build_record(t, j)
            (d / "record.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
            cost = t["agent_usage"]["cost_usd"] + j["judge_usage"]["cost_usd"]
            spent[0] += cost
            return run_id, f"ok  G={rec['scores']['G']} B={rec['scores']['B']} T={rec['scores']['T']} I={rec['scores']['I']} final={rec['scores']['final']}", cost
        except Exception as e:
            (d / "error.txt").write_text(traceback.format_exc())
            return run_id, f"FAILED: {e}", 0.0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for f in as_completed([ex.submit(do, j) for j in jobs]):
            rid, status, cost = f.result()
            print(f"{rid}: {status}  (${cost:.3f}; total ${spent[0]:.2f})", flush=True)
    print("\nPilot runs finished. Next: python -m swarm_pilot.report --runs", args.out)
    print("Phase 2 is NOT started by this script. It waits for the team's approval.")


if __name__ == "__main__":
    main()
