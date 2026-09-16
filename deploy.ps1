# Deploy proxmox-getvm-app to nscc-docker-host
$ErrorActionPreference = "Stop"

$RemoteHost = "nscc-docker-host"
$RemoteDir = "~/proxmox-getvm-app"

Write-Host "Syncing files to ${RemoteHost}:${RemoteDir}..." -ForegroundColor Cyan

# Ensure target directory exists on remote host
ssh $RemoteHost "mkdir -p $RemoteDir/config $RemoteDir/templates $RemoteDir/static"

# Copy project files
scp app.py Dockerfile requirements.txt docker-compose.yml "${RemoteHost}:${RemoteDir}/"
scp config/courses.json "${RemoteHost}:${RemoteDir}/config/"
scp templates/base.html templates/index.html templates/course.html "${RemoteHost}:${RemoteDir}/templates/"
scp static/logo.png "${RemoteHost}:${RemoteDir}/static/"

Write-Host "Files synced successfully." -ForegroundColor Green
Write-Host "To rebuild and restart container on remote host, run:" -ForegroundColor Yellow
Write-Host "  ssh $RemoteHost 'cd $RemoteDir && sudo docker build -t proxmox-getvm-app . && sudo docker stop proxmox-app && sudo docker rm proxmox-app && sudo docker run -d -p 80:5000 --name proxmox-app --env-file .env --restart unless-stopped proxmox-getvm-app'"
