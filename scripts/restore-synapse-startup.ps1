[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$backupKey = 'HKCU:\Software\RazerBatteryStatus\Backup'
$valueName = 'RazerAppEngine'

$backupProperties = Get-ItemProperty -LiteralPath $backupKey -ErrorAction SilentlyContinue
if (
    $null -eq $backupProperties -or
    -not ($backupProperties.PSObject.Properties.Name -contains $valueName)
) {
    throw "No backed-up Razer startup command exists at $backupKey::$valueName"
}
$startupCommand = $backupProperties.PSObject.Properties[$valueName].Value

Set-ItemProperty `
    -LiteralPath $runKey `
    -Name $valueName `
    -Value $startupCommand `
    -Type String
Write-Output 'Restored Razer Synapse current-user auto-start.'
