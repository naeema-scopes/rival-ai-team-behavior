"""Faster Phase 2 runner: games, the second judge and the extra coding all run at the same time (pipelined).

    python -m swarm_pilot.run_phase2_fast --budget 30

Same games, judges, settings and outputs as run_phase2.py; only the scheduling differs:
  * games are started in balanced chunks without waiting for judging to finish;
  * DeepSeek judges each game as soon as its Haiku record exists (persistent worker pool, no batch "passes");
  * verify / disclosure / reasoning / team / reasoning-vs-statement coding run in a loop on new games;
  * the budget is GLOBAL: spend is measured from start_usage in phase2_plan.json (the original launch), so restarting
    never double-counts the $30. A chunk starts only if spend + committed backlog + projected chunk cost ≤ budget.
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import judges as J
from .judge import build_record, judge_run
from .run_phase2 import VARIANTS, credits

PY = [sys.executable, "-m"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--target", type=int, default=64)
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--out", default="phase2")
    ap.add_argument("--game-workers", type=int, default=60)
    ap.add_argument("--judge-workers", type=int, default=40)
    a = ap.parse_args()
    jh, jd = J.parse(J.PHASE2)
    runs, j2, ver, log = Path(f"{a.out}_runs"), Path(f"{a.out}_deepseek"), Path(f"{a.out}_verified"), f"{a.out}_log.txt"
    plan_f = Path(f"{a.out}_plan.json")
    plan = json.loads(plan_f.read_text()) if plan_f.exists() else {}
    start_usage = plan.get("start_usage")
    if start_usage is None:
        start_usage = credits()[0]
        plan_f.write_text(json.dumps(dict(plan, start_usage=start_usage, started=time.ctime()), indent=1))
    j2.mkdir(exist_ok=True)
    cfg = json.loads((runs / "config.json").read_text()) if (runs / "config.json").exists() else {}
    cfg2 = dict(cfg, judge=jd["model"], judge_reasoning_effort=jd["effort"], judge_provider_order=jd["provider"],
                judge_max_tokens=64000, scoring_version="v3", rejudged_from=str(runs))
    (j2 / "config.json").write_text(json.dumps(cfg2, indent=2))
    stop = threading.Event()

    def spent():
        return credits()[0] - start_usage

    # ---- second judge: persistent pool
    pending = set()
    pool = ThreadPoolExecutor(max_workers=a.judge_workers)

    def judge_one(d: Path):
        o = j2 / d.name
        try:
            o.mkdir(exist_ok=True)
            for f in ("transcript.json", "transcript.md", "final_rules.md"):
                (o / f).write_bytes((d / f).read_bytes())
            t = json.loads((d / "transcript.json").read_text())
            j = judge_run(t, jd["model"], cfg2)
            (o / "judge_raw.json").write_text(json.dumps(j, indent=1, ensure_ascii=False))
            (o / "record.json").write_text(json.dumps(build_record(t, j), indent=1, ensure_ascii=False))
        except Exception:
            (o / "error.txt").write_text(traceback.format_exc())
        finally:
            pending.discard(d.name)

    def feeder():
        while not stop.is_set():
            if runs.exists():
                for d in sorted(runs.iterdir()):
                    if (d / "record.json").exists() and not (j2 / d.name / "record.json").exists() and d.name not in pending \
                            and not (j2 / d.name / "error.txt").exists():
                        pending.add(d.name)
                        pool.submit(judge_one, d)
            time.sleep(15)

    # ---- extra coding loop (cached: each pass only codes new games)
    def coder():
        while not stop.is_set():
            with open(log, "a") as fh:
                for args in (["swarm_pilot.verify", "--a", str(runs), "--b", str(j2), "--out", str(ver)],
                             ["swarm_pilot.disclosure", "--runs", str(runs), "--runs2", str(j2), "--out", str(ver)],
                             ["swarm_pilot.reasoning_code", "--runs", str(runs), "--out", str(ver), "--judges", J.PHASE2],
                             ["swarm_pilot.team_dynamics", "--runs", str(runs), "--verified", str(ver), "--judges", J.PHASE2],
                             ["swarm_pilot.cot_mismatch", "--runs", str(runs), "--out", str(ver), "--judges", J.PHASE2]):
                    if stop.is_set():
                        break
                    subprocess.run(PY + args, stdout=fh, stderr=subprocess.STDOUT)
            for _ in range(24):
                if stop.is_set():
                    break
                time.sleep(5)

    threading.Thread(target=feeder, daemon=True).start()
    threading.Thread(target=coder, daemon=True).start()

    # ---- games in balanced chunks, without waiting for judging
    n_var = len(VARIANTS.split(","))
    have = lambda: sum(1 for d in runs.iterdir() if (d / "record.json").exists()) if runs.exists() else 0
    k = max(a.chunk, (have() // n_var) // a.chunk * a.chunk)  # resume at the first incomplete chunk
    k = (have() // n_var) if have() % n_var == 0 and have() // n_var >= k else k
    while True:
        done_now = have()
        k_next = min(a.target, (done_now // n_var) + a.chunk) if done_now % n_var == 0 else min(a.target, -(-done_now // n_var))
        if done_now >= a.target * n_var:
            break
        s = spent()
        per = s / max(1, done_now) if done_now >= 32 else 0.08
        backlog = per * 0.5 * len(pending)                       # unjudged games still to be paid for (≈ half of per-run cost)
        new = k_next * n_var - done_now
        projected = per * 1.25 * new
        if s + backlog + projected > a.budget:
            print(f"STOP before games up to {k_next}/variant: spent ${s:.2f}, backlog ≈ ${backlog:.2f}, next ≈ ${projected:.2f}", flush=True)
            break
        print(f"=== games to {k_next}/variant (done {done_now}, spent ${s:.2f}, ${per:.3f}/game, judge backlog {len(pending)}) ===", flush=True)
        with open(log, "a") as fh:
            subprocess.run(PY + ["swarm_pilot.run_pilot", "--variants", VARIANTS, "--runs-per-variant", str(k_next), "--balanced",
                                 "--out", str(runs), "--workers", str(a.game_workers), "--judge", jh["model"], "--judge-effort", jh["effort"],
                                 "--judge-max-tokens", "64000", "--max-cost", str(max(0.0, a.budget - s - backlog))],
                           stdout=fh, stderr=subprocess.STDOUT)
        print(f"  games done: {have()} (spent ${spent():.2f})", flush=True)
        if have() == done_now:
            print("STOP: no new games completed in this chunk (cost cap or errors); see log", flush=True)
            break

    # ---- drain judging, then final coding and analysis
    print("draining second-judge backlog ...", flush=True)
    while pending:
        time.sleep(15)
    stop.set()
    pool.shutdown(wait=True)
    with open(log, "a") as fh:
        subprocess.run(PY + ["swarm_pilot.rescore", "--runs", str(runs)], stdout=fh, stderr=subprocess.STDOUT)
        for args in (["swarm_pilot.verify", "--a", str(runs), "--b", str(j2), "--out", str(ver)],
                     ["swarm_pilot.disclosure", "--runs", str(runs), "--runs2", str(j2), "--out", str(ver)],
                     ["swarm_pilot.reasoning_code", "--runs", str(runs), "--out", str(ver), "--judges", J.PHASE2],
                     ["swarm_pilot.team_dynamics", "--runs", str(runs), "--verified", str(ver), "--judges", J.PHASE2],
                     ["swarm_pilot.cot_mismatch", "--runs", str(runs), "--out", str(ver), "--judges", J.PHASE2],
                     ["swarm_pilot.fact_disclosure", "--runs", str(runs), "--runs2", str(j2), "--out", str(ver)],
                     ["swarm_pilot.team_splits", "--verified", str(ver)],
                     ["swarm_pilot.role_analysis", "--verified", str(ver), "--runs", str(runs)],
                     ["swarm_pilot.phase2_stats", "--runs", str(runs), "--verified", str(ver)],
                     ["swarm_pilot.primary_analysis", "--runs", str(runs), "--verified", str(ver)]):
            subprocess.run(PY + args, stdout=fh, stderr=subprocess.STDOUT)
    print(f"Phase 2 finished: {have()} games, total spend ${spent():.2f} (budget ${a.budget:.2f}). Outputs in {ver}/", flush=True)


if __name__ == "__main__":
    main()
