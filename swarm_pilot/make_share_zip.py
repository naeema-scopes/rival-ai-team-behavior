"""Package Phase 2 for sharing: plain-language summary, reports, spot-check workbooks, data, readable transcripts, code.

    python -m swarm_pilot.make_share_zip --summary SUMMARY.md --out swarm_experiment_phase2.zip
"""
import argparse
import zipfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--summary", required=True)
ap.add_argument("--out", default="swarm_experiment_phase2.zip")
a = ap.parse_args()
root = Path(".")
ver, runs = root / "phase2_verified", root / "phase2_runs"
files = {
    "README_FIRST_summary.md": Path(a.summary),
    "plan_and_method/PHASE2_PLAN.md": root / "PHASE2_PLAN.md",
    "plan_and_method/METHODOLOGY_AUDIT.md": root / "METHODOLOGY_AUDIT.md",
    "plan_and_method/CHANGES_log.md": root / "CHANGES.md",
    "plan_and_method/brief_v1.md": root / "brief_v1.md",
    "plan_and_method/brief_v2.md": root / "brief_v2.md",
}
reports = ["primary_analysis.md", "stats_report.md", "verification_report.md", "reasoning_report.md", "team_dynamics.md",
           "team_splits.md", "role_analysis.md", "fact_disclosure.md", "flagship_disclosure.md", "cot_mismatch.md"]
for r in reports:
    files[f"reports/{r}"] = ver / r
for p in ver.glob("*.png"):
    files[f"reports/{p.name}"] = p
for r in ("spot_check_sample.md", "spot_check_sample.csv", "spot_check_full.md", "spot_check_full.csv"):
    files[f"spot_check/{r}"] = ver / r
for r in ("analysis_dataset.csv", "company_level.csv", "agent_level.csv", "stats_results.json", "fact_disclosure.json",
          "flagship_disclosure.json", "reasoning_codes.json", "team_dynamics.json", "team_splits.json", "cot_mismatch.json"):
    files[f"data/{r}"] = ver / r
for d in sorted(runs.iterdir()):
    for f in ("transcript.md", "final_rules.md"):
        if (d / f).exists():
            files[f"transcripts/{d.name}/{f}"] = d / f
for p in sorted((root / "swarm_pilot").glob("*.py")):
    files[f"code/swarm_pilot/{p.name}"] = p
files["code/README.md"] = root / "README.md"
missing = [k for k, v in files.items() if not v.exists()]
with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
    for arc, src in files.items():
        if src.exists():
            z.write(src, arc)
print(f"wrote {a.out}: {sum(v.exists() for v in files.values())} files; missing: {missing or 'none'}")
