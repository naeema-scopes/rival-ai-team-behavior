"""Phase 2 runner with a HARD total budget. Do not run until the team has approved Phase 2.

    python -m swarm_pilot.run_phase2 --budget 30            # target 64 runs per variant, stop before exceeding $30
    python -m swarm_pilot.run_phase2 --budget 30 --dry-run   # print the plan only

Works in chunks of balanced blocks (each block = one run of every variant, shuffled). After each chunk it runs the second
judge and all extra coding on the new runs, then reads ACTUAL spend from OpenRouter (/credits). It starts the next chunk
only if spend so far + the projected cost of that chunk (measured cost per run × 1.25 safety margin) stays within budget,
and only if the account has enough credit left. Every variant therefore always has the same number of runs.
Note: /credits is account-wide; avoid using the same OpenRouter account for anything else while this runs.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

from . import judges as J
from .llm import KEY_FILE

VARIANTS = "A,B,D,E,G,H,J,K"
PY = [sys.executable, "-m"]


def credits():
    key = os.environ.get("OPENROUTER_API_KEY") or open(KEY_FILE).read().strip()
    d = requests.get("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"}, timeout=30).json()["data"]
    return float(d["total_usage"]), float(d["total_credits"])


def sh(args, log):
    print("$", " ".join(args), flush=True)
    with open(log, "a") as fh:
        r = subprocess.run(PY + args, stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        print(f"  (exit {r.returncode}; see {log})", flush=True)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=30.0, help="hard cap on total spend for Phase 2 (USD)")
    ap.add_argument("--target", type=int, default=64, help="target runs per variant (power analysis)")
    ap.add_argument("--chunk", type=int, default=8, help="runs per variant added per chunk")
    ap.add_argument("--out", default="phase2")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-section-agreement", type=float, default=0.85,
                    help="stop after the first chunk if the two judges agree on fewer section ratings than this (pilot 3: 0.97)")
    a = ap.parse_args()
    jh, jd = J.parse(J.PHASE2)
    runs, j2, ver = f"{a.out}_runs", f"{a.out}_deepseek", f"{a.out}_verified"
    log = f"{a.out}_log.txt"
    plan = dict(variants=VARIANTS, target_per_variant=a.target, chunk=a.chunk, budget=a.budget, agent_model="openai/gpt-6-luna (low, pinned OpenAI)",
                judge_a=jh, judge_b=jd, folders=dict(runs=runs, judge_b=j2, verified=ver))
    print(json.dumps(plan, indent=1))
    if a.dry_run:
        return
    start_usage, total_credits = credits()
    Path(f"{a.out}_plan.json").write_text(json.dumps(dict(plan, start_usage=start_usage, started=time.ctime()), indent=1))
    done, per_run = 0, None
    while done < a.target:
        k = min(a.target, done + a.chunk)
        used, total_credits = credits()
        spent = used - start_usage
        new_runs = (k - done) * len(VARIANTS.split(","))
        projected = (per_run or 0.096) * 1.25 * new_runs        # before any data: pilot's high-end estimate
        if spent + projected > a.budget or (total_credits - used) < projected:
            print(f"STOP before chunk to {k}/variant: spent ${spent:.2f}, next chunk ≈ ${projected:.2f}, "
                  f"credit left ${total_credits - used:.2f}, budget ${a.budget:.2f}", flush=True)
            break
        print(f"\n=== chunk: {done} → {k} runs per variant (spent so far ${spent:.2f}) ===", flush=True)
        rej = ["swarm_pilot.rejudge", "--src", runs, "--out", j2, "--judge", jd["model"], "--judge-effort", jd["effort"],
               "--judge-provider", jd["provider"][0], "--judge-max-tokens", "64000", "--workers", str(a.workers)]
        print("$ run_pilot (games + Haiku) with DeepSeek judging finished games alongside", flush=True)
        with open(log, "a") as fh:
            games = subprocess.Popen(PY + ["swarm_pilot.run_pilot", "--variants", VARIANTS, "--runs-per-variant", str(k), "--balanced",
                                           "--out", runs, "--workers", str(a.workers), "--judge", jh["model"], "--judge-effort", jh["effort"],
                                           "--judge-max-tokens", "64000", "--max-cost", str(max(0.0, a.budget - spent))],
                                     stdout=fh, stderr=subprocess.STDOUT)
            while games.poll() is None:
                time.sleep(60)
                if Path(runs).exists():
                    subprocess.run(PY + rej, stdout=fh, stderr=subprocess.STDOUT)
        sh(["swarm_pilot.rescore", "--runs", runs], log)
        sh(rej, log)  # final pass for games that finished last
        sh(["swarm_pilot.verify", "--a", runs, "--b", j2, "--out", ver], log)
        sh(["swarm_pilot.disclosure", "--runs", runs, "--runs2", j2, "--out", ver], log)
        sh(["swarm_pilot.reasoning_code", "--runs", runs, "--out", ver, "--judges", J.PHASE2], log)
        sh(["swarm_pilot.team_dynamics", "--runs", runs, "--verified", ver, "--judges", J.PHASE2], log)
        sh(["swarm_pilot.cot_mismatch", "--runs", runs, "--out", ver, "--judges", J.PHASE2], log)
        sh(["swarm_pilot.fact_disclosure", "--runs", runs, "--runs2", j2, "--out", ver], log)
        if done == 0:  # quality gate on the first chunk: is the untested second judge usable?
            V = [json.loads(p.read_text()) for p in Path(ver).glob("[A-Z][0-9][0-9].json")]
            secs = [x["verified"] for v in V for x in v["sections"].values()]
            agree = sum(secs) / max(1, len(secs))
            print(f"  quality gate: section ratings agree between judges in {100 * agree:.0f}% (need ≥ {100 * a.min_section_agreement:.0f}%)", flush=True)
            if agree < a.min_section_agreement:
                print("STOP: the two judges disagree too often on section ratings. Check phase2_verified/verification_report.md "
                      "and spot_check.csv before spending more.", flush=True)
                break
        used2, _ = credits()
        n_done = sum(1 for d in Path(runs).iterdir() if (d / "record.json").exists())
        per_run = (used2 - start_usage) / max(1, n_done)
        done = k
        print(f"  chunk done: {n_done} runs, spent ${used2 - start_usage:.2f}, ${per_run:.3f}/run", flush=True)
    # final, budget-free analysis steps (deterministic or reading cached codes)
    for args in (["swarm_pilot.verify", "--a", runs, "--b", j2, "--out", ver],
                 ["swarm_pilot.disclosure", "--runs", runs, "--runs2", j2, "--out", ver],
                 ["swarm_pilot.fact_disclosure", "--runs", runs, "--runs2", j2, "--out", ver],
                 ["swarm_pilot.team_splits", "--verified", ver],
                 ["swarm_pilot.role_analysis", "--verified", ver, "--runs", runs],
                 ["swarm_pilot.phase2_stats", "--runs", runs, "--verified", ver],
                 ["swarm_pilot.primary_analysis", "--runs", runs, "--verified", ver]):
        sh(args, log)
    used, _ = credits()
    print(f"\nPhase 2 finished: total spend ${used - start_usage:.2f} (budget ${a.budget:.2f}). Outputs in {ver}/")


if __name__ == "__main__":
    main()
