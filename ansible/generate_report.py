#!/usr/bin/env python3
"""
OSYS1200 Lab 2 Audit Report Generator
Reads all JSON audit logs in ./audit_results/ and generates a Markdown summary table.
"""

import glob
import json
import os
import sys

def main():
    results_dir = os.path.join(os.path.dirname(__file__), "audit_results")
    if not os.path.exists(results_dir):
        print(f"[ERROR] Directory '{results_dir}' does not exist. Run audit-lab2.yml first.")
        sys.exit(1)

    json_files = glob.glob(os.path.join(results_dir, "lab2-*.json"))
    if not json_files:
        print(f"[INFO] No audit result files found in '{results_dir}'.")
        sys.exit(0)

    rows = []
    for fpath in sorted(json_files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            student = data.get("Student", "Unknown")
            host = data.get("Host", os.path.basename(fpath))
            score = f"{data.get('PassedCount', 0)}/{data.get('TotalChecks', 6)} ({data.get('ScorePercent', 0)}%)"

            checks = data.get("Checks", {})
            exec_policy = "PASS" if checks.get("ExecutionPolicy", {}).get("Pass") else "FAIL"
            custom_mmc = "PASS" if checks.get("CustomMMC", {}).get("Pass") else "FAIL"
            task_hist = "PASS" if checks.get("TaskSchedulerHistory", {}).get("Pass") else "FAIL"
            script = "PASS" if checks.get("CleanTempScript", {}).get("Pass") else "FAIL"
            task = "PASS" if checks.get("ScheduledTask", {}).get("Pass") else "FAIL"
            autoplay = "PASS" if checks.get("AutoPlay", {}).get("Pass") else "FAIL"

            rows.append({
                "student": student,
                "host": host,
                "score": score,
                "exec": "✅ PASS" if exec_policy == "PASS" else "❌ FAIL",
                "mmc": "✅ PASS" if custom_mmc == "PASS" else "❌ FAIL",
                "hist": "✅ PASS" if task_hist == "PASS" else "❌ FAIL",
                "script": "✅ PASS" if script == "PASS" else "❌ FAIL",
                "task": "✅ PASS" if task == "PASS" else "❌ FAIL",
                "auto": "✅ PASS" if autoplay == "PASS" else "❌ FAIL"
            })
        except Exception as e:
            print(f"[WARNING] Could not parse {fpath}: {e}")

    md_output = []
    md_output.append("# OSYS1200 Lab 2 Automated Audit Report")
    md_output.append(f"**Total VMs Audited:** {len(rows)}\n")
    md_output.append("| Student | Host | Score | Act 8 (Exec Policy) | Act 5 (MMC .msc) | Act 11 (Task History) | Act 12 (Clean Script) | Act 12 (Sched Task) | Act 3 (AutoPlay) |")
    md_output.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

    for r in rows:
        md_output.append(f"| {r['student']} | `{r['host']}` | **{r['score']}** | {r['exec']} | {r['mmc']} | {r['hist']} | {r['script']} | {r['task']} | {r['auto']} |")

    report_content = "\n".join(md_output)
    report_file = os.path.join(os.path.dirname(__file__), "audit_report_lab2.md")
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(report_content)
    print(f"\n[INFO] Saved report to {report_file}")

if __name__ == "__main__":
    main()
