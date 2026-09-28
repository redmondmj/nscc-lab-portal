#!/usr/bin/env python3
"""
OSYS1200 Lab 2 Audit Report Generator
Reads all JSON audit logs in ./audit_results/ and cross-references with dynamic
inventory to display audited and offline/unreachable VMs in a clean Markdown summary.
"""

import glob
import json
import os
import subprocess
import sys

def get_inventory_hosts():
    """Attempts to discover all expected OSYS1200 hosts from inventory.py."""
    inv_script = os.path.join(os.path.dirname(__file__), "inventory.py")
    if not os.path.exists(inv_script):
        return {}

    try:
        proc = subprocess.run(
            [sys.executable, inv_script, "--list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            osys_hosts = set()
            for group in ["osys1200", "osys1200_baseline"]:
                osys_hosts.update(data.get(group, {}).get("hosts", []))
            
            # Map host to student_id from hostvars
            hostvars = data.get("_meta", {}).get("hostvars", {})
            result = {}
            for h in osys_hosts:
                # Filter out generic templates
                if "template" in h.lower() or "test" in h.lower():
                    continue
                sid = hostvars.get(h, {}).get("student_id", h)
                status = hostvars.get(h, {}).get("status", "unknown")
                result[h] = {"student_id": sid, "portal_status": status}
            return result
    except Exception:
        pass
    return {}

def main():
    results_dir = os.path.join(os.path.dirname(__file__), "audit_results")
    if not os.path.exists(results_dir):
        print(f"[ERROR] Directory '{results_dir}' does not exist. Run audit-lab2.yml first.")
        sys.exit(1)

    json_files = glob.glob(os.path.join(results_dir, "lab2-*.json"))
    if not json_files:
        print(f"[INFO] No audit result files found in '{results_dir}'.")
        sys.exit(0)

    # Get known hosts from inventory
    inv_hosts = get_inventory_hosts()
    audited_hosts = set()

    rows = []
    scores = []

    for fpath in sorted(json_files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            student = data.get("Student", "Unknown")
            host = data.get("Host", os.path.basename(fpath).replace("lab2-", "").replace(".json", ""))
            
            # Match host name back to inventory host
            matched_inv_host = None
            for ih in inv_hosts:
                if ih in fpath or ih.lower() == host.lower():
                    matched_inv_host = ih
                    break
            if matched_inv_host:
                audited_hosts.add(matched_inv_host)
            else:
                audited_hosts.add(host)

            passed_count = data.get("PassedCount", 0)
            total_checks = data.get("TotalChecks", 6)
            score_pct = data.get("ScorePercent", 0)
            scores.append(score_pct)
            score_str = f"{passed_count}/{total_checks} ({score_pct}%)"

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
                "status": "ONLINE",
                "score": score_str,
                "exec": "✅ PASS" if exec_policy == "PASS" else "❌ FAIL",
                "mmc": "✅ PASS" if custom_mmc == "PASS" else "❌ FAIL",
                "hist": "✅ PASS" if task_hist == "PASS" else "❌ FAIL",
                "script": "✅ PASS" if script == "PASS" else "❌ FAIL",
                "task": "✅ PASS" if task == "PASS" else "❌ FAIL",
                "auto": "✅ PASS" if autoplay == "PASS" else "❌ FAIL"
            })
        except Exception as e:
            print(f"[WARNING] Could not parse {fpath}: {e}")

    # Add offline hosts if discovered from inventory
    offline_rows = []
    for ih, meta in sorted(inv_hosts.items()):
        if ih not in audited_hosts:
            sid = meta.get("student_id", ih)
            offline_rows.append({
                "student": sid,
                "host": ih,
                "status": "OFFLINE",
                "score": "⚠️ OFFLINE",
                "exec": "—",
                "mmc": "—",
                "hist": "—",
                "script": "—",
                "task": "—",
                "auto": "—"
            })

    all_rows = rows + offline_rows

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    md_output = []
    md_output.append("# OSYS1200 Lab 2 Automated Audit Report")
    md_output.append(f"- **Total Roster Discovered:** {len(all_rows)}")
    md_output.append(f"- **Audited (Online VMs):** {len(rows)}")
    md_output.append(f"- **Offline / Unreachable VMs:** {len(offline_rows)}")
    md_output.append(f"- **Class Average (Audited):** {avg_score}%\n")

    md_output.append("| Student | Host | Score | Act 8 (Exec Policy) | Act 5 (MMC .msc) | Act 11 (Task History) | Act 12 (Clean Script) | Act 12 (Sched Task) | Act 3 (AutoPlay) |")
    md_output.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

    for r in all_rows:
        md_output.append(f"| {r['student']} | `{r['host']}` | **{r['score']}** | {r['exec']} | {r['mmc']} | {r['hist']} | {r['script']} | {r['task']} | {r['auto']} |")

    report_content = "\n".join(md_output)
    report_file = os.path.join(os.path.dirname(__file__), "audit_report_lab2.md")
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(report_content)
    print(f"\n[INFO] Saved report to {report_file}")

if __name__ == "__main__":
    main()
