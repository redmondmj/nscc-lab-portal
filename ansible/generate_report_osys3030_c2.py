#!/usr/bin/env python3
"""
OSYS3030 Challenge 2 Audit Report Generator (Grade-A-Tron)
Reads all JSON audit logs in ./audit_results/ (osys3030-c2-*.json) and cross-references
with dynamic inventory to display audited and offline/unreachable VMs in a clean, compact Markdown summary.
"""

import glob
import json
import os
import subprocess
import sys

def get_inventory_hosts():
    """Discovers all expected OSYS3030 hosts from inventory.py."""
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
            course_hosts = set()
            for group in ["osys3030", "osys3030_baseline"]:
                course_hosts.update(data.get(group, {}).get("hosts", []))

            hostvars = data.get("_meta", {}).get("hostvars", {})
            result = {}
            for h in course_hosts:
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
        os.makedirs(results_dir, exist_ok=True)

    json_files = glob.glob(os.path.join(results_dir, "osys3030-c2-*.json"))
    if not json_files:
        print(f"[INFO] No Challenge 2 audit result files found in '{results_dir}'.")
        print("[HINT] Run: ansible-playbook -i inventory.py audit-osys3030-c2.yml --limit osys3030 -k -K")
        sys.exit(0)

    inv_hosts = get_inventory_hosts()
    audited_hosts = set()

    rows = []
    scores = []

    for fpath in sorted(json_files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            file_host = os.path.basename(fpath).replace("osys3030-c2-", "").replace(".json", "")

            student = data.get("Student", "Unknown")
            if not student or "{{" in student or student == "Unknown":
                if file_host in inv_hosts:
                    student = inv_hosts[file_host].get("student_id", file_host)
                elif "OSYS3030-" in file_host:
                    student = file_host.replace("OSYS3030-", "").replace("-baseline", "")
                else:
                    student = file_host

            audited_hosts.add(file_host)

            checks = data.get("Checks", {})
            c_e18_up = "PASS" if checks.get("Ens18Up", {}).get("Pass") else "FAIL"
            c_e18_gw = "PASS" if checks.get("Ens18Gateway", {}).get("Pass") else "FAIL"
            c_e19_ex = "PASS" if checks.get("Ens19Exists", {}).get("Pass") else "FAIL"
            c_e19_up = "PASS" if checks.get("Ens19Up", {}).get("Pass") else "FAIL"
            c_e19_ip = "PASS" if checks.get("Ens19IP", {}).get("Pass") else "FAIL"
            c_e19_nodf = "PASS" if checks.get("Ens19NoDefault", {}).get("Pass") else "FAIL"
            c_netplan = "PASS" if checks.get("NetplanConfig", {}).get("Pass") else "FAIL"
            c_ping_gw = "PASS" if checks.get("PingGateway", {}).get("Pass") else "FAIL"
            c_ping_in = "PASS" if checks.get("PingInternet", {}).get("Pass") else "FAIL"
            c_dns = "PASS" if checks.get("DNSResolution", {}).get("Pass") else "FAIL"
            c_mtu = "PASS" if checks.get("JumboFrames", {}).get("Pass") else "FAIL"

            eval_list = [c_e18_up, c_e18_gw, c_e19_ex, c_e19_up, c_e19_ip, c_e19_nodf, c_netplan, c_ping_gw, c_ping_in, c_dns, c_mtu]
            passed_count = eval_list.count("PASS")
            total_checks = len(eval_list)
            score_pct = round((passed_count / total_checks) * 100, 1)
            scores.append(score_pct)
            score_str = f"{passed_count}/{total_checks} ({score_pct}%)"

            rows.append({
                "student": student,
                "host": file_host,
                "status": "ONLINE",
                "score": score_str,
                "ens18_up": "✅ PASS" if c_e18_up == "PASS" else "❌ FAIL",
                "ens18_gw": "✅ PASS" if c_e18_gw == "PASS" else "❌ FAIL",
                "ens19_ex": "✅ PASS" if c_e19_ex == "PASS" else "❌ FAIL",
                "ens19_up": "✅ PASS" if c_e19_up == "PASS" else "❌ FAIL",
                "ens19_ip": "✅ PASS" if c_e19_ip == "PASS" else "❌ FAIL",
                "ens19_nodf": "✅ PASS" if c_e19_nodf == "PASS" else "❌ FAIL",
                "netplan": "✅ PASS" if c_netplan == "PASS" else "❌ FAIL",
                "ping_gw": "✅ PASS" if c_ping_gw == "PASS" else "❌ FAIL",
                "ping_in": "✅ PASS" if c_ping_in == "PASS" else "❌ FAIL",
                "dns": "✅ PASS" if c_dns == "PASS" else "❌ FAIL",
                "mtu": "✅ PASS" if c_mtu == "PASS" else "❌ FAIL"
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
                "ens18_up": "—",
                "ens18_gw": "—",
                "ens19_ex": "—",
                "ens19_up": "—",
                "ens19_ip": "—",
                "ens19_nodf": "—",
                "netplan": "—",
                "ping_gw": "—",
                "ping_in": "—",
                "dns": "—",
                "mtu": "—"
            })

    all_rows = rows + offline_rows
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    md_output = []
    md_output.append("# OSYS3030 Challenge 2 Automated Audit Report (Multi-Homed Network)")
    md_output.append(f"- **Total Roster Discovered:** {len(all_rows)}")
    md_output.append(f"- **Audited (Online VMs):** {len(rows)}")
    md_output.append(f"- **Offline / Unreachable VMs:** {len(offline_rows)}")
    md_output.append(f"- **Class Average (Audited):** {avg_score}%\n")

    headers = [
        "Student",
        "Score",
        "e18Up",
        "e18GW",
        "e19Nic",
        "e19Up",
        "e19IP",
        "NoDefGW",
        "Netplan",
        "PingGW",
        "PingNet",
        "DNS",
        "MTU9k"
    ]

    table_data = []
    for r in all_rows:
        score_display = f"**{r['score']}**" if r['status'] == 'ONLINE' else r['score']
        table_data.append([
            r['student'],
            score_display,
            r['ens18_up'],
            r['ens18_gw'],
            r['ens19_ex'],
            r['ens19_up'],
            r['ens19_ip'],
            r['ens19_nodf'],
            r['netplan'],
            r['ping_gw'],
            r['ping_in'],
            r['dns'],
            r['mtu']
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
    report_file = os.path.join(os.path.dirname(__file__), "audit_report_osys3030_c2.md")
    with open(report_file, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    print(report_content)
    print(f"\n[INFO] Saved report to {report_file}")

if __name__ == "__main__":
    main()
