#!/usr/bin/env python3
"""
OSYS1200 Lab 3 Audit Report Generator
Reads all JSON audit logs in ./audit_results/ (lab3-*.json) and cross-references with dynamic
inventory to display audited and offline/unreachable VMs in a clean, compact Markdown summary.
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
            
            hostvars = data.get("_meta", {}).get("hostvars", {})
            result = {}
            for h in osys_hosts:
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
        print(f"[ERROR] Directory '{results_dir}' does not exist. Run audit-lab3.yml first.")
        sys.exit(1)

    json_files = glob.glob(os.path.join(results_dir, "lab3-*.json"))
    if not json_files:
        print(f"[INFO] No Lab 3 audit result files found in '{results_dir}'.")
        print("[HINT] Run: ansible-playbook -i inventory.py audit-lab3.yml --limit osys1200 --ask-pass")
        sys.exit(0)

    inv_hosts = get_inventory_hosts()
    audited_hosts = set()

    rows = []
    scores = []

    for fpath in sorted(json_files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            file_host = os.path.basename(fpath).replace("lab3-", "").replace(".json", "")
            
            student = data.get("Student", "Unknown")
            if not student or "{{" in student or student == "Unknown":
                if file_host in inv_hosts:
                    student = inv_hosts[file_host].get("student_id", file_host)
                elif "OSYS1200-" in file_host:
                    student = file_host.replace("OSYS1200-", "").replace("-baseline", "")
                else:
                    student = file_host

            host = file_host
            audited_hosts.add(file_host)

            checks = data.get("Checks", {})
            u_matt = "PASS" if checks.get("UserMatt", {}).get("Pass") else "FAIL"
            u_jacob = "PASS" if checks.get("UserJacob", {}).get("Pass") else "FAIL"
            grp_test = "PASS" if checks.get("TestGroup", {}).get("Pass") else "FAIL"
            jacob_rdp = "PASS" if checks.get("JacobRDP", {}).get("Pass") else "FAIL"
            ps_hist = "PASS" if checks.get("PSHistory", {}).get("Pass") else "FAIL"
            pub_lnk = "PASS" if checks.get("PublicLnk", {}).get("Pass") else "FAIL"
            start_layout = "PASS" if checks.get("StartLayout", {}).get("Pass") else "FAIL"
            red_team = "PASS" if checks.get("RedTeam", {}).get("Pass") else "FAIL"
            blue_team = "PASS" if checks.get("BlueTeam", {}).get("Pass") else "FAIL"

            eval_list = [u_matt, u_jacob, grp_test, jacob_rdp, ps_hist, pub_lnk, start_layout, red_team, blue_team]
            passed_count = eval_list.count("PASS")
            total_checks = len(eval_list)
            score_pct = round((passed_count / total_checks) * 100, 1)
            scores.append(score_pct)
            score_str = f"{passed_count}/{total_checks} ({score_pct}%)"

            rows.append({
                "student": student,
                "host": host,
                "status": "ONLINE",
                "score": score_str,
                "matt": "✅ PASS" if u_matt == "PASS" else "❌ FAIL",
                "jacob": "✅ PASS" if u_jacob == "PASS" else "❌ FAIL",
                "testgrp": "✅ PASS" if grp_test == "PASS" else "❌ FAIL",
                "rdp": "✅ PASS" if jacob_rdp == "PASS" else "❌ FAIL",
                "history": "✅ PASS" if ps_hist == "PASS" else "❌ FAIL",
                "public": "✅ PASS" if pub_lnk == "PASS" else "❌ FAIL",
                "start": "✅ PASS" if start_layout == "PASS" else "❌ FAIL",
                "red": "✅ PASS" if red_team == "PASS" else "❌ FAIL",
                "blue": "✅ PASS" if blue_team == "PASS" else "❌ FAIL"
            })
        except Exception as e:
            print(f"[WARNING] Could not parse {fpath}: {e}")

    offline_rows = []
    for ih, meta in sorted(inv_hosts.items()):
        if ih not in audited_hosts:
            sid = meta.get("student_id", ih)
            offline_rows.append({
                "student": sid,
                "host": ih,
                "status": "OFFLINE",
                "score": "⚠️ OFFLINE",
                "matt": "—",
                "jacob": "—",
                "testgrp": "—",
                "rdp": "—",
                "history": "—",
                "public": "—",
                "start": "—",
                "red": "—",
                "blue": "—"
            })

    all_rows = rows + offline_rows
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    md_output = []
    md_output.append("# OSYS1200 Lab 3 Automated Audit Report (Users & Groups)")
    md_output.append(f"- **Total Roster Discovered:** {len(all_rows)}")
    md_output.append(f"- **Audited (Online VMs):** {len(rows)}")
    md_output.append(f"- **Offline / Unreachable VMs:** {len(offline_rows)}")
    md_output.append(f"- **Class Average (Audited):** {avg_score}%\n")

    headers = [
        "Student",
        "Score",
        "Matt",
        "Jacob",
        "TestGrp",
        "Jacob RDP",
        "PS History",
        "Public Lnk",
        "Start Layout",
        "Red Team",
        "Blue Team"
    ]

    table_data = []
    for r in all_rows:
        score_display = f"**{r['score']}**" if r['status'] == 'ONLINE' else r['score']
        table_data.append([
            r['student'],
            score_display,
            r['matt'],
            r['jacob'],
            r['testgrp'],
            r['rdp'],
            r['history'],
            r['public'],
            r['start'],
            r['red'],
            r['blue']
        ])

    col_widths = []
    for col_idx in range(len(headers)):
        max_w = len(headers[col_idx])
        for row in table_data:
            max_w = max(max_w, len(str(row[col_idx])))
        col_widths.append(max_w)

    header_line = "| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers))) + " |"
    sep_cols = []
    for i, w in enumerate(col_widths):
        if i == 0:
            sep_cols.append(":" + "-" * (w - 1))
        else:
            sep_cols.append(":" + "-" * (w - 2) + ":")
    sep_line = "| " + " | ".join(sep_cols) + " |"

    md_output.append(header_line)
    md_output.append(sep_line)

    for row in table_data:
        cells = []
        for i, val in enumerate(row):
            w = col_widths[i]
            if i == 0:
                cells.append(str(val).ljust(w))
            else:
                cells.append(str(val).center(w))
        md_output.append("| " + " | ".join(cells) + " |")

    report_content = "\n".join(md_output)
    report_file = os.path.join(os.path.dirname(__file__), "audit_report_lab3.md")
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(report_content)
    print(f"\n[INFO] Saved report to {report_file}")

if __name__ == "__main__":
    main()
