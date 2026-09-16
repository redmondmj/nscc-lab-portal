<#
.SYNOPSIS
    One-time per-machine step: enables WinRM over HTTPS and creates the local
    account Ansible will use going forward, so no further physical touch is
    needed on this machine.

.DESCRIPTION
    Run AFTER Liberate-FromNSCC.ps1, from the USB stick, elevated.
    - Enables PSRemoting and a WinRM HTTPS listener (self-signed cert; this is
      a private lab network, not a public endpoint).
    - Restricts the WinRM HTTPS firewall rule to the Ansible control node's
      address instead of leaving it open to the whole subnet.
    - Creates (or resets the password on) a local admin account dedicated to
      Ansible connections. The password is never hardcoded here - either pass
      it as a SecureString or you'll be prompted. Store the same password in
      ansible-vault on the control node (see ansible/README.md).

.PARAMETER ControlNodeAddress
    IP or hostname of the Ansible control node. Firewall
    rule for WinRM HTTPS is scoped to this address.

.PARAMETER AnsibleUser
    Local account Ansible will connect as. Default: ansible-ops

.PARAMETER AnsiblePassword
    SecureString. If omitted, you'll be prompted (input hidden).

.NOTES
    Must be run as Administrator.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ControlNodeAddress,

    [string]$AnsibleUser = "ansible-ops",

    [System.Security.SecureString]$AnsiblePassword,

    # Set by Run-Full-Migration.ps1 when chaining this into a single-reboot
    # combined run - skips the reboot at the end so the caller can do its own
    # work first and reboot once, not twice.
    [switch]$NoReboot
)

$ErrorActionPreference = 'Stop'

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Not running elevated. Run this via Make Me Admin, as Administrator."
    }
}

Assert-Admin

if (-not $AnsiblePassword) {
    $AnsiblePassword = Read-Host -Prompt "Password for local account '$AnsibleUser'" -AsSecureString
}

# 0. WinRM config (Set-Item on WSMan:\localhost\Service\* in particular) throws
# a terminating error if any connected adapter is classified Public - and a
# freshly-liberated machine defaults to Public, since there's no domain
# controller left around to classify it otherwise. Force it to Private before
# touching anything WinRM/firewall related.
Write-Host "Checking network connection profiles..." -ForegroundColor Cyan
Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' } | ForEach-Object {
    Write-Host "Setting '$($_.Name)' from Public to Private..." -ForegroundColor Cyan
    Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
}

# 1. Local account for Ansible connections
Write-Host "Configuring local account '$AnsibleUser'..." -ForegroundColor Cyan
if (Get-LocalUser -Name $AnsibleUser -ErrorAction SilentlyContinue) {
    Set-LocalUser -Name $AnsibleUser -Password $AnsiblePassword
} else {
    New-LocalUser -Name $AnsibleUser -Password $AnsiblePassword `
        -Description "Ansible control-node connection account" `
        -PasswordNeverExpires:$true
    Add-LocalGroupMember -Group "Administrators" -Member $AnsibleUser
}

# NSCC's GPO/Intune Administrative Templates policy may be locking WinRM's
# Basic-auth setting (blocks `Set-Item WSMan:\localhost\Service\Auth\Basic`
# with "controlled by policies"). This machine is still domain/Entra-managed
# at this point in the process (Liberate hasn't run yet), so remove the
# policy-backed override now, before configuring WinRM - otherwise Set-Item
# below throws. If a background GP refresh hasn't happened yet by the time
# NSCC disconnect completes, this doesn't come back; if it's on-prem AD
# (not just Entra ID) and GP keeps refreshing, this may need reapplying -
# ask whether this machine is on-prem-AD-joined (see dsregcmd /status,
# "DomainJoined" line, separate from "AzureAdJoined") if this recurs.
Remove-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WinRM" -Recurse -Force -ErrorAction SilentlyContinue

# 2. Enable PSRemoting
Write-Host "Enabling PSRemoting..." -ForegroundColor Cyan
Enable-PSRemoting -Force -SkipNetworkProfileCheck

# 3. HTTPS listener with a self-signed cert
Write-Host "Configuring WinRM HTTPS listener..." -ForegroundColor Cyan
$existing = Get-ChildItem WSMan:\localhost\Listener | Where-Object { $_.Keys -contains "Transport=HTTPS" }
if (-not $existing) {
    $cert = New-SelfSignedCertificate -DnsName $env:COMPUTERNAME -CertStoreLocation Cert:\LocalMachine\My -KeyExportPolicy Exportable
    New-Item -Path WSMan:\localhost\Listener -Transport HTTPS -Address * -CertificateThumbPrint $cert.Thumbprint -Force | Out-Null
}

# 4. Firewall - scope WinRM HTTPS to the control node only
Write-Host "Restricting WinRM HTTPS firewall rule to $ControlNodeAddress..." -ForegroundColor Cyan
$ruleName = "WinRM-HTTPS-Ansible"
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 5986 `
    -RemoteAddress $ControlNodeAddress -Action Allow | Out-Null

# Ansible's default connection expects basic auth over the HTTPS listener for
# a local (non-domain) account - enable that, but leave HTTP disabled.
Set-Item -Path WSMan:\localhost\Service\Auth\Basic -Value $true
Set-Item -Path WSMan:\localhost\Service\AllowUnencrypted -Value $false
Disable-PSRemoting -Force 2>$null  # closes the HTTP (5985) listener opened by Enable-PSRemoting
Get-ChildItem WSMan:\localhost\Listener | Where-Object { $_.Keys -contains "Transport=HTTP" } | Remove-Item -Recurse -ErrorAction SilentlyContinue
Enable-PSRemoting -Force -SkipNetworkProfileCheck  # re-enable the service/firewall group without recreating the HTTP listener

Write-Host "`nDone. This machine is reachable over WinRM HTTPS (5986) from $ControlNodeAddress as $AnsibleUser." -ForegroundColor Green
Write-Host "Add it to ansible/inventory/hosts.yml and set the same password in ansible-vault." -ForegroundColor Green

if ($NoReboot) {
    Write-Host "Skipping reboot (-NoReboot) - caller will handle it." -ForegroundColor Yellow
} else {
    Write-Host "Rebooting in 10 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    Restart-Computer
}
