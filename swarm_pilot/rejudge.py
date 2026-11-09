"""Re-judge saved transcripts with a different judge model (agents are NOT re-run).

    python -m swarm_pilot.rejudge --src pilot2_runs --out pilot2_sonnet_runs --judge anthropic/claude-sonnet-5.5
"""
import argparse
import json
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .judge import build_record, judge_run
from .run_pilot import DEFAULTS

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--judge", default="anthropic/claude-sonnet-5.5")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--judge-effort", default=None, help="judge reasoning effort, e.g. max")
ap.add_argument("--judge-provider", default=None, help="pin one provider for the judge, e.g. DeepInfra")
ap.add_argument("--judge-max-tokens", type=int, default=None, help="judge output cap incl. reasoning (128000 for max effort)")
args = ap.parse_args()
src, out = Path(args.src), Path(args.out)
out.mkdir(exist_ok=True)
cfg = json.loads((src / "config.json").read_text())
cfg.update(judge=args.judge, rejudged_from=str(src), judge_max_tokens=args.judge_max_tokens or DEFAULTS["judge_max_tokens"],
           judge_reasoning_effort=args.judge_effort, scoring_version="v3",
           judge_provider_order=[args.judge_provider] if args.judge_provider else None)
(out / "config.json").write_text(json.dumps(cfg, indent=2))


def do(d: Path):
    o = out / d.name
    if (o / "record.json").exists():
        return d.name, "skipped (done)", 0.0
    o.mkdir(exist_ok=True)
    for f in ("transcript.json", "transcript.md", "final_rules.md"):
        shutil.copy(d / f, o / f)
    try:
        t = json.loads((d / "transcript.json").read_text())
        j = judge_run(t, args.judge, cfg)
        (o / "judge_raw.json").write_text(json.dumps(j, indent=1, ensure_ascii=False))
        rec = build_record(t, j)
        (o / "record.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        s = rec["scores"]
        return d.name, f"ok  G={s['G']} B={s['B']} T={s['T']} I={s['I']} final={s['final']}", j["judge_usage"]["cost_usd"]
    except Exception as e:
        (o / "error.txt").write_text(traceback.format_exc())
        return d.name, f"FAILED: {e}", 0.0


dirs = [d for d in sorted(src.iterdir()) if (d / "record.json").exists()]  # only finished runs
total = 0.0
with ThreadPoolExecutor(max_workers=args.workers) as ex:
    for fut in as_completed([ex.submit(do, d) for d in dirs]):
        rid, status, cost = fut.result()
        total += cost
        print(f"{rid}: {status} (judge ${cost:.3f}; total ${total:.2f})", flush=True)
