import unittest
from app import app, db

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
        res = self.client.get("/api/osys1200/status/123456")
        self.assertEqual(res.status_code, 503)
        data = res.get_json()
        self.assertFalse(data["found"])

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
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Faculty Command Center", res.data)
        self.assertIn(b"Instructor Fleet", res.data)
        self.assertIn(b"Dynamic Ansible Inventory", res.data)

    def test_admin_ansible_inventory(self):
        """Test dynamic Ansible inventory endpoint."""
        res = self.client.get("/api/admin/ansible/inventory")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("_meta", data)
        self.assertIn("all", data)
        self.assertIn("osys1200", data)

    def test_admin_template_lifecycle(self):
        """Test adding, updating, and deleting a template via admin API."""
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

        # Patch status
        patch_res = self.client.patch(f"/api/admin/templates/{tmpl_id}", json={
            "is_published": False
        })
        self.assertEqual(patch_res.status_code, 200)
        self.assertFalse(patch_res.get_json()["template"]["is_published"])

        # Delete template
        del_res = self.client.delete(f"/api/admin/templates/{tmpl_id}")
        self.assertEqual(del_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
