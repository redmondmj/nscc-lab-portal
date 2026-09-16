# NSCC Lab Portal (`nscc-lab-portal`)

Multi-course, self-service cloud portal for NSCC students and faculty to provision, manage, and connect to dedicated Proxmox virtual lab machines.

Built for **OSYS1200 (Operating Systems)** with multi-course support (including **NETW2710**).

---

## Features

- **Multi-Course Architecture**:
  - Modular configuration via `config/courses.json`.
  - Dedicated landing page for each course (e.g. `/osys1200`, `/netw2710`).
  - Course-specific branding, instructions, and connection protocols.
- **Windows Lab Optimized (OSYS1200)**:
  - Automatic `.rdp` file generation and download with dynamic IP detection via QEMU guest agent.
  - Virt-Viewer SPICE `.vv` console file generation.
  - Power management (Start VM, Reboot/Restart VM) with real-time status updates without full page reloads.
- **Student-Friendly Input**:
  - Automatically handles student ID formats (e.g., `W01234567` or `1234567`).
- **Production Container Ready**:
  - Containerized with Docker & Gunicorn.
  - Compatible with reverse proxies and Cloudflare Tunnels (`cloudflared`).

---

## Configuration

Copy `.env.example` to `.env` and configure your Proxmox credentials:

```bash
PROXMOX_HOST=10.10.0.11
PROXMOX_API_USER=root@pam
PROXMOX_API_TOKEN_ID=getvm
PROXMOX_API_TOKEN_SECRET=your-secret-uuid
PROXMOX_SPICE_PORT=3128
```

### Adding or Modifying Courses

Edit `config/courses.json`:

```json
{
  "courses": {
    "osys1200": {
      "id": "osys1200",
      "code": "OSYS1200",
      "name": "OSYS1200 - Operating Systems",
      "template_vmid": 2002,
      "preferred_node": "pve2",
      "os_type": "windows",
      "supports_rdp": true,
      "supports_spice": true,
      "default_username": ".\\Student"
    }
  }
}
```

---

## Quickstart (Local Development)

```bash
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate   # (Linux: source venv/bin/activate)

# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
```

Visit [http://localhost:5000](http://localhost:5000).

---

## Deployment via Docker

```bash
# Build and run with docker-compose
docker compose up -d --build
```

Or manually:

```bash
docker build -t proxmox-getvm-app .
docker run -d -p 80:5000 --name proxmox-app --env-file .env --restart unless-stopped proxmox-getvm-app
```
