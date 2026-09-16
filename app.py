import os
import json
import logging
import traceback
from pathlib import Path
from flask import Flask, Response, jsonify, render_template, request, abort

from models import db, Course, LabTemplate, User, StudentVM
from db_init import seed_database, sync_existing_vms_from_proxmox
from provisioner import provision_student_vm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configure SQLite Database
DB_PATH = Path(__file__).parent / "data" / "portal.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH.resolve()}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Initialize and seed database on startup
seed_database(app)

def get_proxmox_client():
    """Initializes and returns a ProxmoxAPI client using environment variables."""
    from proxmoxer import ProxmoxAPI

    proxmox_host = os.environ.get("PROXMOX_HOST", "10.10.0.11")
    api_token_id = os.environ.get("PROXMOX_API_TOKEN_ID")
    api_token_secret = os.environ.get("PROXMOX_API_TOKEN_SECRET")
    api_user_name = os.environ.get("PROXMOX_API_USER", "root@pam")

    if not all([proxmox_host, api_token_id, api_token_secret, api_user_name]):
        logger.warning("Proxmox API environment variables are not fully configured.")
        return None

    return ProxmoxAPI(
        host=proxmox_host,
        user=api_user_name,
        token_name=api_token_id,
        token_value=api_token_secret,
        verify_ssl=False
    )

def find_vm_by_id_or_name(proxmox, student_or_vmid, course=None):
    """
    Finds VM either by exact VMID or by student ID in VM name.
    Returns (node, vmid, vm_resource_dict).
    """
    vmid_str = str(student_or_vmid).strip()
    all_resources = proxmox.cluster.resources.get(type="vm")

    # 1. Direct VM ID match
    for vm in all_resources:
        if str(vm.get("vmid")) == vmid_str and vm.get("type") == "qemu":
            return vm.get("node"), str(vm.get("vmid")), vm

    # 2. Match VM name containing the student ID and course code
    for vm in all_resources:
        name = str(vm.get("name", ""))
        if vmid_str in name and vm.get("type") == "qemu":
            if course and course.code.lower() in name.lower():
                return vm.get("node"), str(vm.get("vmid")), vm
            elif not course:
                return vm.get("node"), str(vm.get("vmid")), vm

    # 3. Secondary pass on any qemu name match
    for vm in all_resources:
        if vmid_str in str(vm.get("name", "")) and vm.get("type") == "qemu":
            return vm.get("node"), str(vm.get("vmid")), vm

    return None, None, None

def get_vm_ip(proxmox, node, vmid):
    """Attempts to fetch the primary IPv4 address via QEMU guest agent."""
    try:
        network_data = proxmox.nodes(node).qemu(vmid).agent("network-get-interfaces").get()
        interfaces = network_data.get("result", [])
        for iface in interfaces:
            if iface.get("name") in ["lo", "docker0"]:
                continue
            for ip_info in iface.get("ip-addresses", []):
                if ip_info.get("ip-address-type") == "ipv4":
                    ip = ip_info.get("ip-address")
                    if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                        return ip
    except Exception:
        pass
    return None

# Sync existing cluster VMs into DB if Proxmox is reachable
try:
    _p = get_proxmox_client()
    if _p:
        sync_existing_vms_from_proxmox(app, _p)
except Exception as e:
    logger.warning(f"Could not perform initial Proxmox VM sync: {e}")

# ==========================================
# Frontend Routes
# ==========================================

@app.route("/")
def index():
    """Renders the course selector page."""
    courses = Course.query.all()
    courses_dict = {c.id: c.to_dict() for c in courses}
    return render_template("index.html", courses=courses_dict)

@app.route("/<course_id>")
def course_portal(course_id):
    """Renders the course-specific student portal."""
    course = db.session.get(Course, course_id.lower())
    if not course:
        abort(404)
    return render_template("course.html", course=course)

# ==========================================
# API Endpoints
# ==========================================

@app.route("/api/<course_id>/templates", methods=["GET"])
def api_list_templates(course_id):
    """Returns published lab templates for a course."""
    course = db.session.get(Course, course_id.lower())
    if not course:
        return jsonify({"error": "Course not found"}), 404

    templates = [t.to_dict() for t in course.templates if t.is_published]
    return jsonify({"course": course.code, "templates": templates})

@app.route("/api/<course_id>/student/<student_id>/vms", methods=["GET"])
def api_student_vms(course_id, student_id):
    """Returns all VMs belonging to a specific student for a course."""
    course = db.session.get(Course, course_id.lower())
    if not course:
        return jsonify({"error": "Course not found"}), 404

    clean_id = student_id.strip()
    vms = StudentVM.query.filter_by(course_id=course.id, user_id=clean_id).all()
    
    # Also check if student has any VM discovered by ID matching
    result = []
    proxmox = get_proxmox_client()

    for vm in vms:
        vm_data = vm.to_dict()
        if proxmox:
            try:
                curr = proxmox.nodes(vm.node).qemu(vm.vmid).status.current.get()
                vm_data["status"] = curr.get("status", "stopped")
                if vm_data["status"] == "running":
                    ip = get_vm_ip(proxmox, vm.node, vm.vmid)
                    if ip:
                        vm_data["ip"] = ip
                        vm.last_ip = ip
                        db.session.commit()
            except Exception:
                pass
        result.append(vm_data)

    return jsonify({
        "student_id": clean_id,
        "course": course.code,
        "vms": result
    })

@app.route("/api/<course_id>/provision", methods=["POST"])
def api_provision_vm(course_id):
    """
    Self-service endpoint: Provisions a new VM for a student from a published template.
    JSON payload: { "student_id": "W0123456", "template_id": 1, "student_name": "Jane Doe" }
    """
    course = db.session.get(Course, course_id.lower())
    if not course:
        return jsonify({"success": False, "error": "Course not found"}), 404

    data = request.get_json() or {}
    student_id = str(data.get("student_id", "")).strip()
    template_id = data.get("template_id")
    student_name = data.get("student_name", student_id)

    if not student_id or not template_id:
        return jsonify({"success": False, "error": "student_id and template_id are required"}), 400

    template = LabTemplate.query.get(template_id)
    if not template or not template.is_published or template.course_id != course.id:
        return jsonify({"success": False, "error": "Invalid or unpublished template selected"}), 400

    # Ensure user exists in DB
    user = User.query.get(student_id)
    if not user:
        user = User(id=student_id, name=student_name, role="student")
        db.session.add(user)
        db.session.commit()

    # Check if student already has a VM from this template (prevent accidental duplicates)
    existing = StudentVM.query.filter_by(
        user_id=student_id,
        course_id=course.id,
        template_id=template.id
    ).first()

    if existing:
        return jsonify({
            "success": False,
            "error": f"You already have a provisioned VM for {template.name} (VM ID {existing.vmid})."
        }), 409

    proxmox = get_proxmox_client()
    if not proxmox:
        return jsonify({"success": False, "error": "Proxmox cluster connection is unavailable."}), 503

    try:
        new_vm = provision_student_vm(
            proxmox=proxmox,
            course=course,
            template=template,
            user=user,
            auto_start=True,
            full_clone=False
        )
        return jsonify({
            "success": True,
            "message": f"Successfully provisioned {new_vm.name} (VM ID {new_vm.vmid})!",
            "vm": new_vm.to_dict()
        }), 201
    except Exception as e:
        logger.error(f"Error provisioning VM for student {student_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/<course_id>/status/<vmid>", methods=["GET"])
def api_vm_status(course_id, vmid):
    """Returns real-time VM power state, host node, and IP."""
    course = db.session.get(Course, course_id.lower())

    proxmox = get_proxmox_client()
    if not proxmox:
        return jsonify({"found": False, "error": "Proxmox connection not configured."}), 503

    try:
        node, real_vmid, vm_res = find_vm_by_id_or_name(proxmox, vmid, course)
        if not node:
            return jsonify({"found": False, "vmid": vmid}), 404

        current_status = proxmox.nodes(node).qemu(real_vmid).status.current.get()
        state = current_status.get("status", "stopped")
        ip = get_vm_ip(proxmox, node, real_vmid) if state == "running" else None

        return jsonify({
            "found": True if node else False,
            "vmid": real_vmid,
            "name": vm_res.get("name", f"VM {real_vmid}"),
            "node": node,
            "status": state,
            "ip": ip,
            "uptime": current_status.get("uptime", 0)
        })
    except Exception as e:
        logger.error(f"Error checking VM status: {e}\n{traceback.format_exc()}")
        return jsonify({"found": False, "error": str(e)}), 500

@app.route("/api/<course_id>/start/<vmid>", methods=["POST"])
def api_start_vm(course_id, vmid):
    """Starts a student VM."""
    course = db.session.get(Course, course_id.lower())

    proxmox = get_proxmox_client()
    if not proxmox:
        return jsonify({"success": False, "error": "Proxmox connection not configured."}), 503

    try:
        node, real_vmid, _ = find_vm_by_id_or_name(proxmox, vmid, course)
        if not node:
            return jsonify({"success": False, "error": f"VM {vmid} not found."}), 404

        current = proxmox.nodes(node).qemu(real_vmid).status.current.get()
        if current.get("status") == "running":
            return jsonify({"success": True, "message": "VM is already running."}), 200

        proxmox.nodes(node).qemu(real_vmid).status.start.post()
        return jsonify({"success": True, "message": f"VM {real_vmid} started."}), 200
    except Exception as e:
        logger.error(f"Error starting VM: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/<course_id>/restart/<vmid>", methods=["POST"])
def api_restart_vm(course_id, vmid):
    """Reboots or resets a student VM."""
    course = db.session.get(Course, course_id.lower())

    proxmox = get_proxmox_client()
    if not proxmox:
        return jsonify({"success": False, "error": "Proxmox connection not configured."}), 503

    try:
        node, real_vmid, _ = find_vm_by_id_or_name(proxmox, vmid, course)
        if not node:
            return jsonify({"success": False, "error": f"VM {vmid} not found."}), 404

        proxmox.nodes(node).qemu(real_vmid).status.reboot.post()
        return jsonify({"success": True, "message": f"VM {real_vmid} reboot command issued."}), 200
    except Exception as e:
        logger.error(f"Error rebooting VM: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/<course_id>/vv/<vmid>", methods=["GET"])
def api_download_vv(course_id, vmid):
    """Generates and downloads Virt-Viewer (.vv) file for SPICE console."""
    course = db.session.get(Course, course_id.lower())

    proxmox = get_proxmox_client()
    if not proxmox:
        abort(503, description="Proxmox connection not configured.")

    try:
        node, real_vmid, _ = find_vm_by_id_or_name(proxmox, vmid, course)
        if not node:
            abort(404, description=f"VM {vmid} not found.")

        proxmox_host = os.environ.get("PROXMOX_HOST", "10.10.0.11")
        spice_port = os.environ.get("PROXMOX_SPICE_PORT", "3128")
        api_response = proxmox.nodes(node).qemu(real_vmid).spiceproxy.post()

        vv_content = f"""[virt-viewer]
host={api_response.get("host")}
proxy=http://{proxmox_host}:{spice_port}
tls-port={api_response.get("tls-port")}
password={api_response.get("password")}
delete-this-file=1
title=VM {real_vmid}
type=spice
ca={api_response.get("ca")}
host-subject={api_response.get("host-subject")}
"""
        return Response(
            vv_content,
            mimetype="application/x-virt-viewer",
            headers={"Content-Disposition": f"attachment;filename=vm_{real_vmid}.vv"}
        )
    except Exception as e:
        logger.error(f"Error generating .vv file: {e}")
        abort(500, description=str(e))

@app.route("/api/<course_id>/rdp/<vmid>", methods=["GET"])
def api_download_rdp(course_id, vmid):
    """Generates and downloads Windows Remote Desktop Connection (.rdp) file."""
    course = Course.query.get(course_id.lower())

    proxmox = get_proxmox_client()
    if not proxmox:
        abort(503, description="Proxmox connection not configured.")

    try:
        node, real_vmid, _ = find_vm_by_id_or_name(proxmox, vmid, course)
        if not node:
            abort(404, description=f"VM {vmid} not found.")

        ip = get_vm_ip(proxmox, node, real_vmid)
        if not ip:
            abort(400, description="VM IP address not yet acquired via guest agent. Please ensure the VM is powered on.")

        default_user = course.default_username if course else ".\\Student"
        rdp_content = f"""full address:s:{ip}
prompt for credentials:i:1
administrative session:i:1
username:s:{default_user}
screen mode id:i:2
use multimon:i:0
span monitors:i:0
desktopwidth:i:1920
desktopheight:i:1080
session bpp:i:32
compression:i:1
keyboardhook:i:2
audiomode:i:0
redirectprinters:i:0
redirectcomports:i:0
redirectsmartcards:i:0
redirectclipboard:i:1
redirectposdevices:i:0
autoreconnection enabled:i:1
authentication level:i:2
enableworkspacereconnect:i:0
gatewayusagemethod:i:0
"""
        return Response(
            rdp_content,
            mimetype="application/x-rdp",
            headers={"Content-Disposition": f"attachment;filename=vm_{real_vmid}.rdp"}
        )
    except Exception as e:
        logger.error(f"Error generating .rdp file: {e}")
        abort(500, description=str(e))

# ==========================================
# Legacy Route Compatibility
# ==========================================

@app.route("/get_vv", methods=["GET"])
def legacy_get_vv():
    vmid = request.args.get("vmid")
    if not vmid:
        abort(400, description="VM ID is required.")
    return api_download_vv("osys1200", vmid)

@app.route("/start_vm", methods=["GET"])
def legacy_start_vm():
    vmid = request.args.get("vmid")
    if not vmid:
        abort(400, description="VM ID is required.")
    return api_start_vm("osys1200", vmid)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
