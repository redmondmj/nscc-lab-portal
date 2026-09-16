# Deploy proxmox-getvm-app to nscc-docker-host
$ErrorActionPreference = "Stop"

$RemoteHost = "nscc-docker-host"
$RemoteDir = "~/proxmox-getvm-app"

Write-Host "Syncing files to ${RemoteHost}:${RemoteDir}..." -ForegroundColor Cyan

# Ensure target directory exists on remote host
ssh $RemoteHost "mkdir -p $RemoteDir/config $RemoteDir/templates $RemoteDir/static $RemoteDir/data $RemoteDir/npm/data $RemoteDir/npm/letsencrypt"

# Copy project files
scp app.py models.py db_init.py provisioner.py auth.py Dockerfile requirements.txt docker-compose.yml "${RemoteHost}:${RemoteDir}/"
scp config/courses.json "${RemoteHost}:${RemoteDir}/config/"
scp templates/*.html "${RemoteHost}:${RemoteDir}/templates/"
scp static/logo.png "${RemoteHost}:${RemoteDir}/static/"

Write-Host "Files synced successfully." -ForegroundColor Green
Write-Host "To launch the full stack (Portal + NPM) on remote host, run:" -ForegroundColor Yellow
Write-Host "  ssh $RemoteHost 'cd $RemoteDir && sudo docker stop proxmox-app 2>/dev/null; sudo docker rm proxmox-app 2>/dev/null; sudo docker compose up -d --build'"
