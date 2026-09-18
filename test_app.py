import unittest
from unittest.mock import patch, MagicMock
from app import app, db, find_vm_by_id_or_name
from models import StudentVM, User, Course, LabTemplate

class TestProxmoxApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_index_route(self):
        """Test main landing page displays courses."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Select Your Course", res.data)
        self.assertIn(b"OSYS1200", res.data)
        self.assertIn(b"NETW2710", res.data)

    def test_osys1200_portal(self):
        """Test OSYS1200 portal loads with Windows-specific elements."""
        res = self.client.get("/osys1200")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"OSYS1200", res.data)
        self.assertIn(b"Remote Desktop (RDP)", res.data)
        self.assertIn(b"Virt-Viewer Console", res.data)

    def test_netw2710_portal(self):
        """Test NETW2710 portal loads with Linux elements."""
        res = self.client.get("/netw2710")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NETW2710", res.data)
        self.assertNotIn(b"Remote Desktop (RDP)", res.data)

    def test_invalid_course_404(self):
        """Test non-existent course returns 404."""
        res = self.client.get("/invalid_course_xyz")
        self.assertEqual(res.status_code, 404)

    def test_api_status_unconfigured(self):
        """Test API returns 503 when Proxmox env vars are missing."""
        import os
        old_token = os.environ.pop("PROXMOX_API_TOKEN_SECRET", None)
        try:
            res = self.client.get("/api/osys1200/status/123456")
            self.assertEqual(res.status_code, 503)
            data = res.get_json()
            self.assertFalse(data["found"])
        finally:
            if old_token:
                os.environ["PROXMOX_API_TOKEN_SECRET"] = old_token

    def test_api_templates_list(self):
        """Test listing published lab templates for OSYS1200."""
        res = self.client.get("/api/osys1200/templates")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("templates", data)
        self.assertGreater(len(data["templates"]), 0)
        tmpl = data["templates"][0]
        self.assertEqual(tmpl["course_id"], "osys1200")
        self.assertEqual(tmpl["template_vmid"], 2002)

    def test_api_student_vms_empty(self):
        """Test fetching student VMs for new student returns empty list."""
        res = self.client.get("/api/osys1200/student/W9999999/vms")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["student_id"], "W9999999")
        self.assertEqual(data["vms"], [])

    def test_api_provision_validation(self):
        """Test validation error when missing payload in provision."""
        res = self.client.post("/api/osys1200/provision", json={})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_admin_dashboard_route(self):
        """Test instructor admin console renders successfully."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Faculty Command Center", res.data)
        self.assertIn(b"Instructor Fleet", res.data)
        self.assertIn(b"Dynamic Ansible Inventory", res.data)

    def test_admin_ansible_inventory(self):
        """Test dynamic Ansible inventory endpoint."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}
        res = self.client.get("/api/admin/ansible/inventory")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("_meta", data)
        self.assertIn("all", data)
        self.assertIn("osys1200", data)

    def test_admin_template_lifecycle(self):
        """Test adding, updating, and deleting a template via admin API."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}

        # Add template
        add_res = self.client.post("/api/admin/templates", json={
            "course_id": "osys1200",
            "template_vmid": 2005,
            "name": "Lab 5 Storage Spaces",
            "description": "Test template",
            "os_type": "windows"
        })
        self.assertEqual(add_res.status_code, 201)
        tmpl_id = add_res.get_json()["template"]["id"]

        # Patch status and update password/credentials
        patch_res = self.client.patch(f"/api/admin/templates/{tmpl_id}", json={
            "is_published": False,
            "default_password": "NewSecretPassphrase!",
            "default_username": ".\\LabUser",
            "preferred_node": "pve"
        })
        self.assertEqual(patch_res.status_code, 200)
        updated_data = patch_res.get_json()["template"]
        self.assertFalse(updated_data["is_published"])
        self.assertEqual(updated_data["default_password"], "NewSecretPassphrase!")
        self.assertEqual(updated_data["default_username"], ".\\LabUser")
        self.assertEqual(updated_data["preferred_node"], "pve")

        # Also test PUT method
        put_res = self.client.put(f"/api/admin/templates/{tmpl_id}", json={
            "name": "Lab 5 Storage Spaces Updated",
            "default_password": "Learn2=work=machine"
        })
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.get_json()["template"]["default_password"], "Learn2=work=machine")

        # Delete template
        del_res = self.client.delete(f"/api/admin/templates/{tmpl_id}")
        self.assertEqual(del_res.status_code, 200)

    def test_api_me_unauthenticated(self):
        """Test /api/me returns unauthenticated status when no session exists."""
        res = self.client.get("/api/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["authenticated"])
        self.assertIsNone(data["user"])

    def test_api_me_authenticated(self):
        """Test /api/me returns user data when session is active."""
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": "W0123456",
                "name": "Test Student",
                "email": "w0123456@nscc.ca",
                "role": "student"
            }
        res = self.client.get("/api/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["id"], "W0123456")
        self.assertEqual(data["user"]["role"], "student")

    def test_logout(self):
        """Test /logout clears user session and redirects to index."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0123456", "name": "Student", "role": "student"}
        res = self.client.get("/logout")
        self.assertEqual(res.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user", sess)

    def test_admin_rbac_with_sso_enabled(self):
        """Test RBAC on admin console when SSO is configured."""
        import os
        old_client_id = os.environ.get("ENTRA_CLIENT_ID")
        try:
            os.environ["ENTRA_CLIENT_ID"] = "mock-client-id"

            # 1. Unauthenticated -> Redirects to /login
            res_anon = self.client.get("/admin")
            self.assertEqual(res_anon.status_code, 302)
            self.assertIn("/login", res_anon.headers.get("Location", ""))

            # 2. Authenticated as Student -> 403 Forbidden
            with self.client.session_transaction() as sess:
                sess["user"] = {"id": "W0123456", "name": "Student", "role": "student"}
            res_student = self.client.get("/admin")
            self.assertEqual(res_student.status_code, 403)

            # 3. Authenticated as Instructor -> 200 OK
            with self.client.session_transaction() as sess:
                sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}
            res_instructor = self.client.get("/admin")
            self.assertEqual(res_instructor.status_code, 200)
            self.assertIn(b"Faculty Command Center", res_instructor.data)
        finally:
            if old_client_id is not None:
                os.environ["ENTRA_CLIENT_ID"] = old_client_id
            else:
                os.environ.pop("ENTRA_CLIENT_ID", None)

    def test_student_isolation(self):
        """Test students cannot view or provision for other student IDs."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0123456", "name": "Student A", "role": "student"}

        # Attempt to access Student B's VMs
        res = self.client.get("/api/osys1200/student/W0987654/vms")
        self.assertEqual(res.status_code, 403)

        # Attempt to access own VMs
        res_own = self.client.get("/api/osys1200/student/W0123456/vms")
        self.assertEqual(res_own.status_code, 200)

    def test_login_redirect(self):
        """Test /login redirects to Microsoft Entra ID authorization endpoint."""
        import os
        res = self.client.get("/login")
        if os.environ.get("ENTRA_CLIENT_ID"):
            self.assertEqual(res.status_code, 302)
            self.assertIn("login.microsoftonline.com", res.headers.get("Location", ""))

    def test_guacamole_token_generation(self):
        """Test AES-256 token encryption for guacamole-lite."""
        import base64
        import json
        from app import generate_guacamole_token
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        secret = "test-secret-key-for-guacamole-12"
        settings = {
            "connection": {
                "type": "rdp",
                "settings": {
                    "hostname": "10.10.0.211",
                    "port": "3389"
                }
            }
        }

        token = generate_guacamole_token(settings, secret)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 50)

        # Decrypt to verify round-trip
        envelope = json.loads(base64.b64decode(token).decode("utf-8"))
        self.assertIn("iv", envelope)
        self.assertIn("value", envelope)

        key_bytes = secret[:32].ljust(32, "0").encode("utf-8")
        iv = base64.b64decode(envelope["iv"])
        ciphertext = base64.b64decode(envelope["value"])

        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_plain = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plain = unpadder.update(padded_plain) + unpadder.finalize()
        decrypted_obj = json.loads(plain.decode("utf-8"))

        self.assertEqual(decrypted_obj["connection"]["type"], "rdp")
        self.assertEqual(decrypted_obj["connection"]["settings"]["hostname"], "10.10.0.211")

    def test_template_password_privacy(self):
        """Verify lab template passwords are never exposed in public to_dict()."""
        from models import LabTemplate
        tmpl = LabTemplate(
            course_id="osys1200",
            template_vmid=2002,
            name="Test Template",
            slug="test-tmpl",
            default_username="student",
            default_password="SecretPassword123"
        )
        public_dict = tmpl.to_dict()
        self.assertNotIn("default_password", public_dict)

        admin_dict = tmpl.to_dict(include_sensitive=True)
        self.assertIn("default_password", admin_dict)
        self.assertEqual(admin_dict["default_password"], "SecretPassword123")

    def test_guacamole_ssh_token(self):
        """Test generating SSH connection token for Linux VMs/containers."""
        import base64
        import json
        from app import generate_guacamole_token

        secret = "test-secret-key-for-guacamole-12"
        settings = {
            "connection": {
                "type": "ssh",
                "settings": {
                    "hostname": "10.10.0.250",
                    "port": "22",
                    "username": "student",
                    "password": "SecretPassword123"
                }
            }
        }
        token = generate_guacamole_token(settings, secret)
        self.assertIsInstance(token, str)

    def test_claims_extraction_first_last(self):
        """Test extracting student ID as first.last from @nscctruro.ca accounts."""
        from auth import extract_user_from_claims
        claims = {
            "preferred_username": "cameron.harris@nscctruro.ca",
            "name": "Cameron Harris"
        }
        user = extract_user_from_claims(claims)
        self.assertEqual(user["id"], "cameron.harris")
        self.assertEqual(user["email"], "cameron.harris@nscctruro.ca")
        self.assertEqual(user["name"], "Cameron Harris")
        self.assertEqual(user["role"], "student")

    def test_claims_extraction_wnumber(self):
        """Test extracting student ID as W# from standard college accounts."""
        from auth import extract_user_from_claims
        claims = {
            "preferred_username": "w0492817@nscc.ca",
            "name": "Jane Student"
        }
        user = extract_user_from_claims(claims)
        self.assertEqual(user["id"], "W0492817")
        self.assertEqual(user["role"], "student")

    def test_user_cohort_model(self):
        """Test User model cohort column serialization."""
        from models import User
        u = User(
            id="test.student",
            name="Test Student",
            email="test.student@nscctruro.ca",
            role="student",
            cohort="Lab-Y1-ITSM"
        )
        data = u.to_dict()
        self.assertEqual(data["cohort"], "Lab-Y1-ITSM")
        self.assertEqual(data["id"], "test.student")

    def test_admin_cohorts_api(self):
        """Test /api/admin/cohorts endpoint returns grouped cohorts."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}
        res = self.client.get("/api/admin/cohorts")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("cohorts", data)
        self.assertIn("total", data)

    def test_admin_enroll_and_unenroll(self):
        """Test enrolling and removing a student from a course."""
        from models import User, Enrollment
        with app.app_context():
            u = User.query.get("test.enrollee")
            if not u:
                u = User(id="test.enrollee", name="Enrollee", email="test.enrollee@nscctruro.ca")
                db.session.add(u)
                db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}

        # 1. Enroll student
        res = self.client.post("/api/admin/enroll", json={
            "user_id": "test.enrollee",
            "course_id": "osys1200"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["enrolled_count"], 1)

        # 2. Verify enrolled in User.to_dict()
        with app.app_context():
            u = db.session.get(User, "test.enrollee")
            self.assertIn("osys1200", u.to_dict()["enrolled_courses"])

        # 3. Unenroll student
        res = self.client.post("/api/admin/unenroll", json={
            "user_id": "test.enrollee",
            "course_id": "osys1200"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["removed_count"], 1)

        # 4. Verify removed
        with app.app_context():
            u = db.session.get(User, "test.enrollee")
            self.assertNotIn("osys1200", u.to_dict()["enrolled_courses"])

    def test_admin_course_crud_lifecycle(self):
        """Test creating, editing, and deleting a course via admin APIs."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"id": "W0999999", "name": "Prof. Smith", "role": "instructor"}

        # 1. Create a new course
        course_data = {
            "id": "csci4000",
            "code": "CSCI4000",
            "name": "CSCI4000 - Cloud Architecture",
            "subtitle": "Kubernetes & Containers Lab",
            "badge": "K8s / Linux",
            "description": "Multi-node lab environment.",
            "preferred_node": "pve",
            "default_username": "cloudadmin",
            "supports_rdp": False,
            "supports_spice": True,
            "custom_notes": "Step 1: Install k3s\nStep 2: Connect via Virt-Viewer (`winget install RedHat.VirtViewer`)"
        }
        res = self.client.post("/api/admin/courses", json=course_data)
        self.assertEqual(res.status_code, 201)
        created = res.get_json()["course"]
        self.assertEqual(created["id"], "csci4000")
        self.assertEqual(created["code"], "CSCI4000")
        self.assertIn("Step 1: Install k3s", created["custom_notes"])

        # 2. Duplicate check
        dup_res = self.client.post("/api/admin/courses", json=course_data)
        self.assertEqual(dup_res.status_code, 409)

        # 3. View course portal renders custom notes
        view_res = self.client.get("/csci4000")
        self.assertEqual(view_res.status_code, 200)
        self.assertIn(b"CSCI4000", view_res.data)
        self.assertIn(b"Step 1: Install k3s", view_res.data)
        self.assertIn(b"<code>winget install RedHat.VirtViewer</code>", view_res.data)

        # 4. Edit course
        edit_res = self.client.put("/api/admin/courses/csci4000", json={
            "name": "CSCI4000 - Advanced Cloud Computing",
            "custom_notes": "Updated note with **bold instructions**."
        })
        self.assertEqual(edit_res.status_code, 200)
        updated = edit_res.get_json()["course"]
        self.assertEqual(updated["name"], "CSCI4000 - Advanced Cloud Computing")
        self.assertEqual(updated["custom_notes"], "Updated note with **bold instructions**.")

        # Verify updated note renders bold in portal
        view_updated = self.client.get("/csci4000")
        self.assertIn(b"<strong>bold instructions</strong>", view_updated.data)

        # 5. Delete course
        del_res = self.client.delete("/api/admin/courses/csci4000")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json()["success"])

        # Verify gone
        gone_res = self.client.get("/csci4000")
        self.assertEqual(gone_res.status_code, 404)

        # 6. Verify course deletion is prevented when active student VMs exist
        del_active_res = self.client.delete("/api/admin/courses/osys1200")
        self.assertEqual(del_active_res.status_code, 400)
        self.assertIn("Cannot delete course", del_active_res.get_json()["error"])

    @patch("app.get_proxmox_client")
    def test_cdrom_eject_and_mount(self, mock_get_proxmox):
        mock_p = MagicMock()
        mock_get_proxmox.return_value = mock_p

        mock_p.cluster.resources.get.return_value = [
            {"vmid": 2002, "node": "pve2", "name": "OSYS1200-W0123456-Lab1", "type": "qemu"}
        ]
        mock_p.nodes("pve2").qemu("2002").config.get.return_value = {
            "ide2": "local:iso/ubuntu-26.04.1-live-server-amd64.iso,media=cdrom",
            "boot": "order=ide2;scsi0"
        }

        # Test GET /api/cluster/isos
        mock_p.nodes.return_value.storage.get.return_value = [{"storage": "local", "content": "iso"}]
        mock_p.nodes.return_value.storage.return_value.content.get.return_value = [
            {"volid": "local:iso/ubuntu-26.04.1.iso", "size": 2000000000, "format": "iso"}
        ]

        res_isos = self.client.get("/api/cluster/isos?node=pve")
        self.assertEqual(res_isos.status_code, 200)
        data = res_isos.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(any("ubuntu-26.04.1.iso" in x["filename"] for x in data["isos"]))

        # Test POST eject
        res_eject = self.client.post("/api/osys1200/cdrom/2002", json={"action": "eject"})
        self.assertEqual(res_eject.status_code, 200)
        self.assertTrue(res_eject.get_json()["success"])
        mock_p.nodes("pve2").qemu("2002").config.post.assert_called_with(
            ide2="none,media=cdrom", boot="order=scsi0;net0"
        )

        # Test POST mount
        res_mount = self.client.post("/api/osys1200/cdrom/2002", json={
            "action": "mount",
            "iso": "local:iso/ubuntu-26.04.1.iso",
            "boot_first": True
        })
        self.assertEqual(res_mount.status_code, 200)
        self.assertTrue(res_mount.get_json()["success"])
        mock_p.nodes("pve2").qemu("2002").config.post.assert_called_with(
            ide2="local:iso/ubuntu-26.04.1.iso,media=cdrom", boot="order=ide2;scsi0;net0"
        )

    def test_course_vm_isolation_and_multiple_vms(self):
        """Verify student VMs are strictly isolated by course and multiple VMs are returned."""
        with app.app_context():
            # Create user and ensure courses exist
            u = User.query.get("W0777777")
            if not u:
                u = User(id="W0777777", name="Multi VM Student", role="student")
                db.session.add(u)
                db.session.commit()

            c_osys = db.session.get(Course, "osys1200")
            c_other = db.session.get(Course, "osys3030")
            if not c_other:
                c_other = Course(id="osys3030", code="OSYS3030", name="Network Linux", os_type="linux")
                db.session.add(c_other)
                db.session.commit()

            tmpl = LabTemplate.query.filter_by(course_id="osys1200").first()

            # Clean any old test records
            StudentVM.query.filter_by(user_id="W0777777").delete()
            db.session.commit()

            # Add two VMs for osys1200
            vm1 = StudentVM(user_id="W0777777", course_id="osys1200", template_id=tmpl.id, vmid=7001, name="OSYS1200-W0777777-Lab1", node="pve")
            vm2 = StudentVM(user_id="W0777777", course_id="osys1200", template_id=tmpl.id, vmid=7002, name="OSYS1200-W0777777-Lab2", node="pve")
            # Add one VM for osys3030
            vm3 = StudentVM(user_id="W0777777", course_id="osys3030", template_id=tmpl.id, vmid=7003, name="OSYS3030-W0777777-Lab1", node="pve")
            db.session.add_all([vm1, vm2, vm3])
            db.session.commit()

        # Query osys1200 student VMs endpoint
        res = self.client.get("/api/osys1200/student/W0777777/vms")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        returned_vmids = [v["vmid"] for v in data["vms"]]

        # Must return both osys1200 VMs (multiple VMs supported)
        self.assertEqual(len(data["vms"]), 2)
        self.assertIn(7001, returned_vmids)
        self.assertIn(7002, returned_vmids)

        # Must NOT leak the osys3030 VM into osys1200
        self.assertNotIn(7003, returned_vmids)

        # Test find_vm_by_id_or_name course isolation
        with app.app_context():
            c_osys = db.session.get(Course, "osys1200")
            mock_p = MagicMock()
            mock_p.cluster.resources.get.return_value = [
                {"vmid": 7003, "node": "pve", "name": "OSYS3030-W0777777-Lab1", "type": "qemu"}
            ]
            # When querying under osys1200, matching a student ID should NOT match a VM belonging to osys3030
            node, real_vmid, _ = find_vm_by_id_or_name(mock_p, "W0777777", course=c_osys)
            self.assertIsNone(node)
            self.assertIsNone(real_vmid)

if __name__ == "__main__":
    unittest.main()
