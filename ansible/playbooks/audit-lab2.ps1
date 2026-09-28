$results = [ordered]@{
    Host = $env:COMPUTERNAME
    Student = "{{ student_id | default('Unknown') }}"
    Checks = [ordered]@{}
}

# -------------------------------------------------------------
# 1. Activity 8: PowerShell Execution Policy
# -------------------------------------------------------------
$policy = Get-ExecutionPolicy
$policyPass = ($policy -eq "RemoteSigned" -or $policy -eq "Unrestricted" -or $policy -eq "Bypass")
$results.Checks["ExecutionPolicy"] = [ordered]@{
    Activity = "Activity 8 (PowerShell Execution Policy)"
    Status = "$policy"
    Pass = $policyPass
}

# -------------------------------------------------------------
# 2. Activity 5: MMC Saved Console (*.msc on Student profile/disks)
# -------------------------------------------------------------
$searchPaths = @(
    "C:\Users\Student\Desktop",
    "C:\Users\Student\OneDrive\Desktop",
    "C:\Users\Student\Documents",
    "C:\Users\Student\OneDrive\Documents",
    "C:\Users\Student\Downloads",
    "C:\Users\Student",
    "C:\"
) | Where-Object { Test-Path $_ }

$mscFiles = Get-ChildItem -Path $searchPaths -Filter "*.msc" -Depth 3 -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "Windows|Program Files|AppData|SysWOW64|system32" } |
    Select-Object -ExpandProperty FullName -Unique

$mscPass = ($mscFiles.Count -gt 0)
$results.Checks["CustomMMC"] = [ordered]@{
    Activity = "Activity 5 (Custom MMC Snap-in .msc)"
    Files = if ($mscFiles) { @($mscFiles) } else { @() }
    Pass = $mscPass
}

# -------------------------------------------------------------
# 3. Activity 11: Task Scheduler History Enabled
# -------------------------------------------------------------
try {
    $taskLog = Get-WinEvent -ListLog "Microsoft-Windows-TaskScheduler/Operational" -ErrorAction Stop
    $historyEnabled = [bool]$taskLog.IsEnabled
} catch {
    $historyEnabled = $false
}
$results.Checks["TaskSchedulerHistory"] = [ordered]@{
    Activity = "Activity 11 (Task Scheduler History Logging)"
    Enabled = $historyEnabled
    Pass = $historyEnabled
}

# -------------------------------------------------------------
# 4. Activity 12: CleanTemp.ps1 Script File & C:\AppTemp
# -------------------------------------------------------------
$candidateScripts = @(
    "C:\Scripts\CleanTemp.ps1",
    "C:\Scripts\*.ps1",
    "C:\AppTemp\CleanTemp.ps1",
    "C:\CleanTemp.ps1",
    "C:\Users\Student\Desktop\CleanTemp.ps1",
    "C:\Users\Student\CleanTemp.ps1"
)
$foundScript = $null
$scriptContentValid = $false

foreach ($p in $candidateScripts) {
    $matched = Get-Item -Path $p -ErrorAction SilentlyContinue
    if ($matched) {
        $foundScript = $matched[0].FullName
        $content = Get-Content $foundScript -Raw -ErrorAction SilentlyContinue
        if ($content -match "AppTemp|Remove-Item") {
            $scriptContentValid = $true
            break
        }
    }
}

$appTempExists = (Test-Path "C:\AppTemp") -or (Test-Path "C:\Temp")
$scriptPass = ([bool]$foundScript -and $scriptContentValid)

$results.Checks["CleanTempScript"] = [ordered]@{
    Activity = "Activity 12 (CleanTemp.ps1 & C:\AppTemp)"
    ScriptFound = $foundScript
    ScriptValid = $scriptContentValid
    AppTempDirExists = $appTempExists
    Pass = $scriptPass
}

# -------------------------------------------------------------
# 5. Activity 12: Scheduled Task (Clean Application Temp Files)
# -------------------------------------------------------------
$allTasks = Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskPath -notmatch "Microsoft" }

$targetTask = $allTasks | Where-Object { $_.TaskName -eq "Clean Application Temp Files" }
if (-not $targetTask) {
    $targetTask = $allTasks | Where-Object {
        $_.TaskName -match "Clean|Temp" -or
        ($_.Actions | Where-Object { $_.Arguments -match "CleanTemp|AppTemp" })
    } | Select-Object -First 1
}

if ($targetTask) {
    $taskInfo = Get-ScheduledTaskInfo -TaskName $targetTask.TaskName -TaskPath $targetTask.TaskPath -ErrorAction SilentlyContinue
    $isSystem = [bool]($targetTask.Principal.UserId -match "SYSTEM|S-1-5-18")
    $hasScriptAction = [bool]($targetTask.Actions | Where-Object { $_.Arguments -match "CleanTemp|\.ps1" -or $_.Execute -match "powershell" })
    $lastResult = if ($taskInfo) { $taskInfo.LastTaskResult } else { -1 }
    $taskPass = ($hasScriptAction -or $isSystem)

    $results.Checks["ScheduledTask"] = [ordered]@{
        Activity = "Activity 12 (Scheduled Task)"
        TaskName = $targetTask.TaskName
        RunsAsUser = $targetTask.Principal.UserId
        ActionPointsToScript = $hasScriptAction
        LastRunResult = $lastResult
        Pass = $taskPass
    }
} else {
    $results.Checks["ScheduledTask"] = [ordered]@{
        Activity = "Activity 12 (Scheduled Task)"
        Exists = $false
        Pass = $false
    }
}

# -------------------------------------------------------------
# 6. Activity 3: AutoPlay Configuration (StorageOnArrival)
# -------------------------------------------------------------
$autoPlayPass = $false
$foundHandler = ""

$userSids = Get-ChildItem Registry::HKEY_USERS -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match "^S-1-5-21-[0-9-]+$" } |
    Select-Object -ExpandProperty PSChildName

foreach ($sid in $userSids) {
    $basePath = "Registry::HKEY_USERS\$sid\Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers"
    
    $chosenPath = "$basePath\UserChosenExecuteHandlers"
    if (Test-Path $chosenPath) {
        $subKeys = Get-ChildItem $chosenPath -ErrorAction SilentlyContinue
        foreach ($sk in $subKeys) {
            $val = (Get-ItemProperty $sk.PSPath -ErrorAction SilentlyContinue).'(default)'
            if ($val -match "OpenFolder|MSOpenFolder") {
                $autoPlayPass = $true
                $foundHandler = "$($sk.PSChildName): $val"
                break
            }
        }
    }

    $defaultPath = "$basePath\EventHandlersDefaultSelection"
    if (Test-Path $defaultPath) {
        $subKeys = Get-ChildItem $defaultPath -ErrorAction SilentlyContinue
        foreach ($sk in $subKeys) {
            $val = (Get-ItemProperty $sk.PSPath -ErrorAction SilentlyContinue).'(default)'
            if ($val -match "OpenFolder|MSOpenFolder") {
                $autoPlayPass = $true
                $foundHandler = "$($sk.PSChildName): $val"
                break
            }
        }
    }

    if ($autoPlayPass) { break }
}

$results.Checks["AutoPlay"] = [ordered]@{
    Activity = "Activity 3 (AutoPlay Settings)"
    Handler = $foundHandler
    Pass = $autoPlayPass
}

$passed = @($results.Checks.Keys | Where-Object { $results.Checks[$_].Pass -eq $true }).Count
$total = $results.Checks.Count
$results["PassedCount"] = $passed
$results["TotalChecks"] = $total
$results["ScorePercent"] = [math]::Round(($passed / $total) * 100, 1)

$results | ConvertTo-Json -Depth 5
