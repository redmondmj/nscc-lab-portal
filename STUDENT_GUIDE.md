# Student Quick-Start Guide: NSCC Virtual Lab Portal

Welcome to the **NSCC Virtual Lab Portal**! This portal provides dedicated, high-performance virtual lab machines hosted on our on-premise Proxmox & Ceph virtualization cluster.

---

## Step 1: Set Up Remote Access (Cloudflare WARP)
> 💡 **On-Campus Note**: If you are working from a physical computer inside **Lab 312**, you are already on the local lab network and can skip directly to **Step 2**.

If you are working from your personal laptop, home network, or campus Wi-Fi, you need the Cloudflare Zero Trust (WARP) client to route securely to your private lab VM:

1. **Download & Install Cloudflare WARP**:
   - Visit [**https://one.dash.cloudflare.com**](https://one.dash.cloudflare.com) or [**https://1.1.1.1**](https://1.1.1.1) and download the client for Windows, macOS, or Linux.
2. **Connect to the Institutional Organization**:
   - Open the Cloudflare WARP app on your device.
   - Go to **Settings (Gear icon) &rarr; Account &rarr; Login with Cloudflare Zero Trust**.
   - When prompted for your team name, enter:
     ```text
     nscctruro
     ```
   - Enter your official NSCC student email address (`@nscc.ca` or `@nscctruro.ca`).
   - Check your student email inbox for a **6-digit one-time PIN code** and enter it.
3. **Turn ON WARP**:
   - Toggle the main switch to **Connected** (*Zero Trust*).
   - Your device is now securely connected to the lab network.

---

## Step 2: Log in to the Lab Portal

1. Open your web browser and navigate to:
   👉 [**https://labs.nscctruro.ca**](https://labs.nscctruro.ca)
2. Click **Sign in with Microsoft**.
3. Log in using your **`@nscctruro.ca`** account.
4. Once authenticated, select your course from the navigation bar or course list (e.g., **OSYS1200** or **OSYS3030**).

---

## Step 3: Provision Your Lab VM

1. On your course page, you will see the available lab environments published by your instructor.
2. Click **Provision Lab VM** (for example, *Windows 11 Baseline* in OSYS1200).
3. The system will perform an instant copy-on-write clone on our distributed Ceph storage cluster.
4. Within **15–30 seconds**, your dedicated VM card will appear with its live status, VM ID, and assigned private IP address (`10.20.x.x`).

---

## Step 4: Connecting to Your Virtual Machine

You have two convenient ways to interact with your VM:

### Method A: In-Browser Web Console *(Zero Software Install)*
- Click **Open Console** on your VM card.
- A new browser tab will launch an interactive desktop console.
- Works on any device: Windows, Mac, Linux, Chromebook, or iPad.

### Method B: Direct Native Remote Desktop (RDP) *(Recommended for Windows Labs)*
- Ensure Cloudflare WARP is **Connected** (or you are in Lab 312).
- Click **Download RDP** on your VM card.
- Open the downloaded `.rdp` file with Windows Remote Desktop Connection (or *Microsoft Remote Desktop* on macOS).
- Log in with the default credentials:
  - **Username**: `.\Student`
  - **Password**: *(Provided by your instructor during class)*
- Enjoy native multi-monitor support, smooth 60 FPS display, shared clipboard, and local audio.

### Method C: SSH Terminal *(For Linux Labs / OSYS3030)*
- If you are running a Linux lab, open your terminal (PowerShell, Command Prompt, or macOS Terminal) and run:
  ```bash
  ssh student@<your-vm-ip>
  ```

### Method D: Virt-Viewer / SPICE Console *(Direct Hypervisor Display)*
- **When to use**: If the operating system is still booting, if you need BIOS/bootloader access, or if you encounter network or display adapter issues with RDP.
- **Client Installation (One-Time Setup)**:
  - **Windows**: Open PowerShell or Windows Terminal and run:
    ```powershell
    winget install RedHat.VirtViewer
    ```
  - **macOS**: Open Terminal and run:
    ```bash
    brew install virt-viewer
    ```
  - **Linux (Debian/Ubuntu)**: Run `sudo apt install virt-viewer`
- **Connecting**:
  - Click **📡 Virt-Viewer** on your VM card to download the `.vv` connection file.
  - Open the downloaded `.vv` file—Virt-Viewer will launch and connect directly to your VM's hardware console over SPICE.

---

## Step 5: Managing Your VM Lifecycle

- **Start / Stop / Restart**: You have full control over your VM's power state using the buttons on your VM card.
- **Saving Resources**: When you finish your lab work for the day, please **Stop / Shut down** your VM from the portal or from the Windows Start menu to conserve campus compute resources.
- **Persistent Data**: Your VM disk state and files are permanently saved to our Ceph storage pool—everything will be exactly as you left it when you start it back up next class.

---

## Troubleshooting & FAQ

- **"Cannot reach https://labs.nscctruro.ca or RDP connection times out"**:
  - Verify that Cloudflare WARP is running and says **Connected** to organization **`nscctruro`**.
- **"Sign-in Error / Tenant Conflict"**:
  - Ensure you are signing in with your **`@nscctruro.ca`** account, rather than a personal Microsoft account.
- **"My course page says I have no enrolled courses"**:
  - Notify your instructor so they can verify your account is assigned to your course cohort in the Admin console.
