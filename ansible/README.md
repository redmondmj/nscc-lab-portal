# Windows VM Template Preparation (Ansible & WinRM)

This directory contains scripts and playbooks to bootstrap and prepare Windows virtual machines before converting them to Proxmox templates for the Lab Portal.

---

## Files

- **`Bootstrap-WinRM-Ansible.ps1`**: Run once inside the Windows VM to enable PSRemoting/WinRM over HTTPS (port 5986), create or update the local admin (`sysop`), generate self-signed cert, and scope the firewall.
- **`vm-template-prep.yml`**: Ansible playbook that configures:
  - Local `sysop` admin membership
  - Disables AC standby, sleep, hibernate, and display timeouts
  - Sets Windows Update to notify-only (`AUOptions = 2`)
  - Enables Remote Desktop (`fDenyTSConnections = 0`)
  - Disables NLA (`UserAuthentication = 0`) for Guacamole and direct RDP
  - Configures Windows Firewall for RDP (3389) and ICMP Ping
  - Ensures `QEMU-GA` (Guest Agent) is set to Automatic and running
  - Purges temporary directories and flushes DNS cache
- **`hosts.yml.example`**: Example inventory configuration.
- **`ansible.cfg`**: Default Ansible configuration.

---

## Step-by-Step Template Prep Workflow

### 1. Bootstrap WinRM inside the VM (PowerShell as Admin)

```powershell
.\Bootstrap-WinRM-Ansible.ps1 -ControlNodeAddress <YOUR_CONTROL_NODE_IP> -AnsibleUser "sysop"
```

### 2. Configure Inventory

Copy `hosts.yml.example` to `hosts.yml` and set the VM's current Lab IP:

```bash
cp hosts.yml.example hosts.yml
```

### 3. Run the Playbook

From this directory:

```bash
ansible-playbook vm-template-prep.yml --ask-pass
```

### 4. Proxmox Finalization

1. Shut down the VM cleanly.
2. In Proxmox, under **Hardware**:
   - Double-check **Network Device (net0)**: `Bridge: vmbr2`, `VLAN Tag: 20`.
   - Move all virtual disks (`scsi0`, `scsi1`, `EFI Disk`, `TPM State`) to **`Ceph_VM_Storage`** (with *Delete source* checked).
3. Right-click the VM &rarr; **Convert to template**.
