# Proxmox Lab Portal — Ansible Automation & Inventory

This directory provides Ansible playbooks, configuration, and tools for two distinct purposes:
1. **Live Fleet Management**: Managing actively deployed student VMs in real-time via the portal's dynamic inventory API (`inventory.py`).
2. **Template Preparation**: Bootstrapping and sysprepping Windows VMs before converting them to golden Proxmox templates (`vm-template-prep.yml`).

---

## 1. Live Fleet Management (Dynamic Inventory)

Student VMs receive dynamic DHCP addresses on VLAN 20 and can be created or destroyed at will. Rather than maintaining a static inventory file, Ansible queries the Lab Portal API dynamically.

### Setup
Ensure your `ANSIBLE_API_KEY` is defined in your environment or in a root `.env` file:
```bash
export ANSIBLE_API_KEY="your-secure-ansible-api-key"
# Optional (defaults to https://labs.nscctruro.ca):
export LAB_PORTAL_URL="https://labs.nscctruro.ca"
```

### Usage Examples
The default `ansible.cfg` points directly to `./inventory.py`. You can run commands without manual `-i` flags, or pass `-i inventory.py` explicitly:

```bash
# Test connectivity to all active student VMs in the lab:
ansible all -m win_ping

# Target all students enrolled in OSYS1200:
ansible osys1200 -m win_ping

# Run an audit or maintenance playbook on a specific course fleet:
ansible-playbook playbooks/audit_lab.yml --limit osys1200

# Inspect the live JSON inventory graph:
ansible-inventory --graph
```

#### Automated Host Variables
For Windows VMs, `inventory.py` automatically injects the required WinRM parameters:
- `ansible_host`: Current IP reported by QEMU Guest Agent (e.g. `10.20.1.X`)
- `ansible_connection`: `winrm`
- `ansible_port`: `5986` (HTTPS)
- `ansible_winrm_transport`: `basic`
- `ansible_winrm_server_cert_validation`: `ignore`
- `ansible_user`: `.\\Student` or template default

---

## 2. Golden Template Preparation (Static Workflow)

When creating a new base VM to convert into a golden template, use this one-time staging workflow.

### Files
- **`Bootstrap-WinRM-Ansible.ps1`**: Run once inside the Windows VM to enable PSRemoting/WinRM over HTTPS (port 5986), create or update the local admin (`sysop`), generate a self-signed cert, and scope the firewall.
- **`vm-template-prep.yml`**: Ansible playbook that configures:
  - Local `sysop` admin membership
  - Disables AC standby, sleep, hibernate, and display timeouts
  - Sets Windows Update to notify-only (`AUOptions = 2`)
  - Enables Remote Desktop (`fDenyTSConnections = 0`)
  - Disables NLA (`UserAuthentication = 0`) for Guacamole and direct RDP
  - Configures Windows Firewall for RDP (3389) and ICMP Ping
  - Ensures `QEMU-GA` (Guest Agent) is set to Automatic and running
  - Purges temporary directories and flushes DNS cache
- **`hosts.yml.example`**: Example static inventory configuration.

### Step-by-Step Template Prep

#### Step 1: Bootstrap WinRM inside the VM (PowerShell as Administrator)
```powershell
.\Bootstrap-WinRM-Ansible.ps1 -ControlNodeAddress <YOUR_CONTROL_NODE_IP> -AnsibleUser "sysop"
```

#### Step 2: Configure Staging Inventory
Copy `hosts.yml.example` to `hosts.yml` and set the staging VM's temporary IP:
```bash
cp hosts.yml.example hosts.yml
```

#### Step 3: Run the Playbook
```bash
ansible-playbook -i hosts.yml vm-template-prep.yml --ask-pass
```

#### Step 4: Finalize in Proxmox
1. Shut down the VM cleanly.
2. In Proxmox, under **Hardware**:
   - Double-check **Network Device (net0)**: `Bridge: vmbr2`, `VLAN Tag: 20`.
   - Move all virtual disks (`scsi0`, `scsi1`, `EFI Disk`, `TPM State`) to **`Ceph_VM_Storage`** (with *Delete source* checked).
3. Right-click the VM &rarr; **Convert to template**.
