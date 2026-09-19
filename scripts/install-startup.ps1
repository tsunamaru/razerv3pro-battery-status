[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskName = 'Razer Battery Status'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonw = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'

if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    throw "The uv environment does not exist. Run 'uv sync --dev' in $projectRoot first."
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument '-m razer_battery_status monitor' `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "Installed and started scheduled task: $taskName"

$synapseRunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$synapseStartup = Get-ItemProperty `
    -LiteralPath $synapseRunKey `
    -Name 'RazerAppEngine' `
    -ErrorAction SilentlyContinue
if ($null -ne $synapseStartup) {
    Write-Warning 'Razer Synapse is configured to start at logon and can contend for HID responses. Disable its auto-start or uninstall it.'
}
