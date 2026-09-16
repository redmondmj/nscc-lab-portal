import os
import json
import logging
from pathlib import Path
from models import db, Course, LabTemplate, User, StudentVM

logger = logging.getLogger(__name__)

def seed_database(app):
    """Initializes tables and seeds initial courses/templates from config/courses.json."""
    with app.app_context():
        db.create_all()

        config_file = Path(app.root_path) / "config" / "courses.json"
        if not config_file.exists():
            logger.warning("config/courses.json not found, skipping seeding.")
            return

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                courses_dict = data.get("courses", {})

            for course_id, cdata in courses_dict.items():
                course = Course.query.get(course_id)
                if not course:
                    course = Course(
                        id=course_id,
                        code=cdata.get("code", course_id.upper()),
                        name=cdata.get("name", course_id.upper()),
                        subtitle=cdata.get("subtitle", ""),
                        badge=cdata.get("badge", ""),
                        description=cdata.get("description", ""),
                        preferred_node=cdata.get("preferred_node", "pve2"),
                        default_username=cdata.get("default_username", ".\\Student"),
                        supports_rdp=cdata.get("supports_rdp", True),
                        supports_spice=cdata.get("supports_spice", True)
                    )
                    db.session.add(course)
                    db.session.flush()

                # Seed primary template if template_vmid is defined
                tmpl_vmid = cdata.get("template_vmid")
                if tmpl_vmid:
                    existing_tmpl = LabTemplate.query.filter_by(
                        course_id=course.id,
                        template_vmid=tmpl_vmid
                    ).first()

                    if not existing_tmpl:
                        new_tmpl = LabTemplate(
                            course_id=course.id,
                            template_vmid=tmpl_vmid,
                            name=f"{course.code} Baseline Lab",
                            slug="baseline",
                            description=cdata.get("description", "Standard course lab virtual machine."),
                            os_type=cdata.get("os_type", "windows"),
                            supports_rdp=cdata.get("supports_rdp", True),
                            supports_spice=cdata.get("supports_spice", True),
                            preferred_node=cdata.get("preferred_node", "pve2"),
                            default_username=cdata.get("default_username", ".\\Student"),
                            is_published=True
                        )
                        db.session.add(new_tmpl)

            db.session.commit()
            logger.info("Database initialized and seeded successfully.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error seeding database: {e}")

def sync_existing_vms_from_proxmox(app, proxmox):
    """
    Scans the Proxmox cluster for existing VMs matching course conventions
    and registers them into the database so existing student VMs are preserved.
    """
    if not proxmox:
        return

    with app.app_context():
        try:
            all_vms = proxmox.cluster.resources.get(type="vm")
            courses = {c.code.lower(): c for c in Course.query.all()}

            for vm in all_vms:
                if vm.get("type") != "qemu":
                    continue

                name = vm.get("name", "")
                vmid = vm.get("vmid")
                node = vm.get("node")

                # Check if name contains a known course code (e.g. OSYS1200 or NETW2710)
                matched_course = None
                for ccode, course_obj in courses.items():
                    if ccode in name.lower():
                        matched_course = course_obj
                        break

                if matched_course:
                    # Check if already in DB
                    existing = StudentVM.query.filter_by(vmid=vmid).first()
                    if not existing:
                        # Extract student ID if in name (e.g. NETW2710-RobertAtkinson or OSYS1200-W0123456)
                        parts = name.split("-")
                        student_identifier = parts[1] if len(parts) > 1 else f"user_{vmid}"
                        
                        user = User.query.get(student_identifier)
                        if not user:
                            user = User(
                                id=student_identifier,
                                name=student_identifier,
                                role="student"
                            )
                            db.session.add(user)
                            db.session.flush()

                        tmpl = LabTemplate.query.filter_by(course_id=matched_course.id).first()
                        if tmpl:
                            record = StudentVM(
                                user_id=user.id,
                                course_id=matched_course.id,
                                template_id=tmpl.id,
                                vmid=vmid,
                                name=name,
                                node=node,
                                status=vm.get("status", "stopped")
                            )
                            db.session.add(record)

            db.session.commit()
            logger.info("Successfully synchronized existing cluster VMs with database.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error syncing VMs from Proxmox: {e}")
