import unittest
from app import app

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
        self.assertIn(b"Connect via RDP", res.data)
        self.assertIn(b"Virt-Viewer", res.data)

    def test_netw2710_portal(self):
        """Test NETW2710 portal loads with Linux elements."""
        res = self.client.get("/netw2710")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NETW2710", res.data)
        self.assertNotIn(b"Connect via RDP", res.data)

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

if __name__ == "__main__":
    unittest.main()
