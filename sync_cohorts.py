import os
import json
import logging
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

from models import db, User, StudentVM, Course, LabTemplate, Enrollment

logger = logging.getLogger(__name__)

COHORT_GROUPS = [
    "Lab-Y1-ITSM",
    "Lab-Y1-Web",
    "Lab-Y2-ITSM",
    "Lab-Y2-Web"
]

import shutil

def fetch_group_members_via_az(group_name):
    """Queries Entra ID for members of a specified security group using az cli."""
    az_bin = shutil.which("az") or "az"
    cmd = [az_bin, "ad", "group", "member", "list", "--group", group_name, "-o", "json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=(os.name == "nt"))
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to query group '{group_name}' via az cli: {e.stderr}")
        return []
    except Exception as e:
        logger.error(f"Error fetching group members for '{group_name}': {e}")
        return []

def sync_entra_cohorts(app=None, groups=None):
    """
    Synchronizes Entra ID cohort groups into the portal database.
    Upserts User records with username (first.last), email, display name, and cohort tag.
    """
    if groups is None:
        groups = COHORT_GROUPS

    results = {
        "synced_count": 0,
        "cohorts": {},
        "errors": []
    }

    def _sync():
        for group in groups:
            members = fetch_group_members_via_az(group)
            results["cohorts"][group] = len(members)
            for m in members:
                upn = (m.get("userPrincipalName") or m.get("mail") or "").strip().lower()
                display_name = (m.get("displayName") or "").strip()
                if not upn or "@" not in upn:
                    continue

                username = upn.split("@")[0].lower()
                user = db.session.get(User, username)
                if not user:
                    user = User(
                        id=username,
                        email=upn,
                        name=display_name or username.title(),
                        role="student",
                        cohort=group
                    )
                    db.session.add(user)
                    results["synced_count"] += 1
                else:
                    if display_name:
                        user.name = display_name
                    user.email = upn
                    user.cohort = group
                    results["synced_count"] += 1
                # Auto-enroll in cohort default courses
                target_courses = []
                if "Y1" in group:
                    target_courses.append("osys1200")
                if "Y2" in group:
                    target_courses.append("netw2710")
                    if "ITSM" in group:
                        target_courses.append("osys3030")
                for cid in target_courses:
                    if not Enrollment.query.filter_by(user_id=username, course_id=cid).first():
                        db.session.add(Enrollment(user_id=username, course_id=cid))

        db.session.commit()
        logger.info(f"Cohort sync complete: {results['synced_count']} student records updated.")

    if app:
        with app.app_context():
            _sync()
    else:
        _sync()

    return results

if __name__ == "__main__":
    import sys
    from app import app, get_proxmox_client
    from db_init import sync_existing_vms_from_proxmox

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("Starting Entra ID Cohort Synchronization...")
    res = sync_entra_cohorts(app)
    print(f"Sync Results: {res['synced_count']} records processed across {len(res['cohorts'])} cohorts:")
    for c, count in res["cohorts"].items():
        print(f"  • {c}: {count} students")

    # Also sync Proxmox VMs to match students
    try:
        proxmox = get_proxmox_client()
        if proxmox:
            print("Synchronizing existing Proxmox cluster VMs with updated student accounts...")
            sync_existing_vms_from_proxmox(app, proxmox)
            print("Proxmox cluster VM synchronization finished.")
    except Exception as e:
        print(f"Note: Proxmox sync skipped: {e}")
