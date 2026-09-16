import time
import logging
from datetime import datetime, timezone
from models import db, StudentVM

logger = logging.getLogger(__name__)

def wait_for_proxmox_task(proxmox, node, upid, timeout=180, poll_interval=2):
    """Polls a Proxmox task UPID until finished or timed out."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            status = proxmox.nodes(node).tasks(upid).status.get()
            if status.get("status") == "stopped":
                exitstatus = status.get("exitstatus")
                if exitstatus == "OK":
                    logger.info(f"Proxmox task {upid} completed successfully.")
                    return True, "OK"
                else:
                    logger.error(f"Proxmox task {upid} failed with status: {exitstatus}")
                    return False, exitstatus
        except Exception as e:
            logger.warning(f"Error checking task {upid}: {e}")
        time.sleep(poll_interval)

    logger.error(f"Proxmox task {upid} timed out after {timeout} seconds.")
    return False, "TIMEOUT"

def provision_student_vm(proxmox, course, template, user, auto_start=True, full_clone=False):
    """
    Provisions a new VM for a student from a published LabTemplate.
    - Allocates next available cluster VMID via proxmox.cluster.nextid.get()
    - Clones template on preferred node
    - Configures tags, names, and description
    - Optionally starts VM and waits for guest agent IP
    """
    node = template.preferred_node or course.preferred_node or "pve2"
    source_vmid = template.template_vmid

    # 1. Allocate next unused VMID from cluster
    try:
        new_vmid = int(proxmox.cluster.nextid.get())
    except Exception as e:
        logger.error(f"Failed to retrieve nextid from Proxmox: {e}")
        raise RuntimeError(f"Proxmox cluster could not allocate next VM ID: {e}")

    # 2. Format name and tags
    clean_user = user.id.replace(" ", "")
    vm_name = f"{course.code}-{clean_user}-{template.slug}"[:64]
    tags = f"{course.id};{clean_user.lower()};{template.slug}"

    logger.info(f"Cloning template {source_vmid} to new VM {new_vmid} ({vm_name}) on node {node}...")

    # 3. Post clone task
    clone_params = {
        "newid": new_vmid,
        "name": vm_name,
        "full": 1 if full_clone else 0
    }
    
    try:
        task_upid = proxmox.nodes(node).qemu(source_vmid).clone.post(**clone_params)
    except Exception as e:
        logger.error(f"Clone API call failed: {e}")
        raise RuntimeError(f"Proxmox clone operation failed: {e}")

    # 4. Wait for clone task to complete
    success, exitstatus = wait_for_proxmox_task(proxmox, node, task_upid, timeout=240)
    if not success:
        raise RuntimeError(f"VM cloning failed: {exitstatus}")

    # 5. Apply tags and metadata
    try:
        proxmox.nodes(node).qemu(new_vmid).config.post(
            tags=tags,
            description=f"Course: {course.name}\nStudent: {user.name} ({user.id})\nTemplate: {template.name}\nProvisioned: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    except Exception as e:
        logger.warning(f"Could not set tags/description on VM {new_vmid}: {e}")

    # 6. Record in Database
    student_vm = StudentVM(
        user_id=user.id,
        course_id=course.id,
        template_id=template.id,
        vmid=new_vmid,
        name=vm_name,
        node=node,
        status="stopped"
    )
    db.session.add(student_vm)
    db.session.commit()

    # 7. Start VM if requested
    if auto_start:
        try:
            logger.info(f"Auto-starting provisioned VM {new_vmid}...")
            proxmox.nodes(node).qemu(new_vmid).status.start.post()
            student_vm.status = "running"
            db.session.commit()
        except Exception as e:
            logger.warning(f"Could not auto-start VM {new_vmid}: {e}")

    return student_vm
