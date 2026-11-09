"""Re-score existing runs from their saved transcript + judge output (no API calls).

    python -m swarm_pilot.rescore --runs pilot2_runs
"""
import argparse
import json
from pathlib import Path

from .judge import build_record

ap = argparse.ArgumentParser()
ap.add_argument("--runs", required=True)
args = ap.parse_args()
n = 0
for d in sorted(Path(args.runs).iterdir()):
    if (d / "transcript.json").exists() and (d / "judge_raw.json").exists():
        t = json.loads((d / "transcript.json").read_text())
        j = json.loads((d / "judge_raw.json").read_text())
        (d / "record.json").write_text(json.dumps(build_record(t, j), indent=1, ensure_ascii=False))
        n += 1
print(f"re-scored {n} runs")
