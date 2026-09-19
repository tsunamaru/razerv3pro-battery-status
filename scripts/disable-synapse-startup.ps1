[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$backupKey = 'HKCU:\Software\RazerBatteryStatus\Backup'
$valueName = 'RazerAppEngine'

$runProperties = Get-ItemProperty -LiteralPath $runKey
if (-not ($runProperties.PSObject.Properties.Name -contains $valueName)) {
    Write-Output 'Razer Synapse current-user auto-start is already disabled.'
    exit 0
}
$startupCommand = $runProperties.PSObject.Properties[$valueName].Value

New-Item -Path $backupKey -Force | Out-Null
Set-ItemProperty `
    -LiteralPath $backupKey `
    -Name $valueName `
    -Value $startupCommand `
    -Type String
Remove-ItemProperty -LiteralPath $runKey -Name $valueName

Write-Output 'Disabled Razer Synapse current-user auto-start.'
Write-Output "The original command is backed up at $backupKey::$valueName"
