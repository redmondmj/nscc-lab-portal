$results = [ordered]@{
    Host = $env:COMPUTERNAME
    Student = "{{ student_id | default('Unknown') }}"
    Checks = [ordered]@{}
}

# -------------------------------------------------------------
# 1. Activity 1: User 'Matt'
# -------------------------------------------------------------
try {
    $uMatt = Get-LocalUser -Name "Matt" -ErrorAction Stop
    $mattNameOk = ($uMatt.FullName -eq "Matt Redmond")
    $mattPass = [bool]($uMatt -and $mattNameOk)
} catch {
    $mattPass = $false
}
$results.Checks["UserMatt"] = [ordered]@{
    Activity = "Act 1 (User 'Matt')"
    Pass = $mattPass
}

# -------------------------------------------------------------
# 2. Activity 1: User 'Jacob'
# -------------------------------------------------------------
try {
    $uJacob = Get-LocalUser -Name "Jacob" -ErrorAction Stop
    $jacobNameOk = ($uJacob.FullName -eq "Jacob Smith")
    $jacobDescOk = ($uJacob.Description -eq "Test User Account")
    $jacobPass = [bool]($uJacob -and $jacobNameOk)
} catch {
    $jacobPass = $false
}
$results.Checks["UserJacob"] = [ordered]@{
    Activity = "Act 1 (User 'Jacob')"
    Pass = $jacobPass
}

# -------------------------------------------------------------
# 3. Activity 1: Group 'TestGroup' & Jacob Membership
# -------------------------------------------------------------
try {
    $gTest = Get-LocalGroup -Name "TestGroup" -ErrorAction Stop
    $members = Get-LocalGroupMember -Group "TestGroup" -ErrorAction SilentlyContinue
    $isMember = [bool](@($members.Name) | Where-Object { $_ -like "*\Jacob" })
    $testGroupPass = [bool]($gTest -and $isMember)
} catch {
    $testGroupPass = $false
}
$results.Checks["TestGroup"] = [ordered]@{
    Activity = "Act 1 (TestGroup w/ Jacob)"
    Pass = $testGroupPass
}

# -------------------------------------------------------------
# 4. Activity 1: Jacob in 'Remote Desktop Users'
# -------------------------------------------------------------
try {
    $rdpMembers = Get-LocalGroupMember -Group "Remote Desktop Users" -ErrorAction Stop
    $jacobRdpPass = [bool](@($rdpMembers.Name) | Where-Object { $_ -like "*\Jacob" })
} catch {
    $jacobRdpPass = $false
}
$results.Checks["JacobRDP"] = [ordered]@{
    Activity = "Act 1 (Jacob in RDP Users)"
    Pass = $jacobRdpPass
}

# -------------------------------------------------------------
# 5. Activity 2: ps-history.txt in Documents
# -------------------------------------------------------------
$historyPaths = @(
    "C:\Users\Student\Documents\ps-history.txt",
    "C:\Users\Student\OneDrive\Documents\ps-history.txt",
    "C:\Users\Student\Desktop\ps-history.txt"
)
$historyPass = $false
foreach ($hp in $historyPaths) {
    if (Test-Path $hp) {
        $historyPass = $true
        break
    }
}
$results.Checks["PSHistory"] = [ordered]@{
    Activity = "Act 2 (ps-history.txt)"
    Pass = $historyPass
}

# -------------------------------------------------------------
# 6. Activity 3: Public Desktop Shortcut (*.lnk)
# -------------------------------------------------------------
$publicDesktop = "C:\Users\Public\Desktop"
$shortcuts = Get-ChildItem -Path $publicDesktop -Filter "*.lnk" -Force -ErrorAction SilentlyContinue
$publicLnkPass = ($shortcuts.Count -gt 0)
$results.Checks["PublicLnk"] = [ordered]@{
    Activity = "Act 3 (Public Desktop .lnk)"
    Pass = [bool]$publicLnkPass
}

# -------------------------------------------------------------
# 7. Activity 4: StartMenuLayout.json in C:\Start
# -------------------------------------------------------------
$startLayoutPass = (Test-Path "C:\Start\StartMenuLayout.json")
$results.Checks["StartLayout"] = [ordered]@{
    Activity = "Act 4 (StartMenuLayout.json)"
    Pass = [bool]$startLayoutPass
}

# -------------------------------------------------------------
# 8. Activity 5: Group 'redteam'
# -------------------------------------------------------------
try {
    $gRed = Get-LocalGroup -Name "redteam" -ErrorAction Stop
    $hasRedDesc = -not ([string]::IsNullOrWhiteSpace($gRed.Description))
    $redteamPass = [bool]($gRed -and $hasRedDesc)
} catch {
    $redteamPass = $false
}
$results.Checks["RedTeam"] = [ordered]@{
    Activity = "Act 5 (Group 'redteam')"
    Pass = $redteamPass
}

# -------------------------------------------------------------
# 9. Activity 5: Group 'blueteam' & Jacob Membership
# -------------------------------------------------------------
try {
    $gBlue = Get-LocalGroup -Name "blueteam" -ErrorAction Stop
    $hasBlueDesc = -not ([string]::IsNullOrWhiteSpace($gBlue.Description))
    $blueMembers = Get-LocalGroupMember -Group "blueteam" -ErrorAction SilentlyContinue
    $isBlueMember = [bool](@($blueMembers.Name) | Where-Object { $_ -like "*\Jacob" })
    $blueteamPass = [bool]($gBlue -and $hasBlueDesc -and $isBlueMember)
} catch {
    $blueteamPass = $false
}
$results.Checks["BlueTeam"] = [ordered]@{
    Activity = "Act 5 (Group 'blueteam' w/ Jacob)"
    Pass = $blueteamPass
}

# Calculate Score
$passed = @($results.Checks.Keys | Where-Object { $results.Checks[$_].Pass -eq $true }).Count
$total = $results.Checks.Count
$results["PassedCount"] = $passed
$results["TotalChecks"] = $total
$results["ScorePercent"] = [math]::Round(($passed / $total) * 100, 1)

$results | ConvertTo-Json -Depth 5
