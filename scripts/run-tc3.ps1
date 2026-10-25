param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
function Read-SecretValue([string]$PromptText) {
    $secretInput = Read-Host $PromptText -AsSecureString
    $credentialValue = New-Object System.Net.NetworkCredential('', $secretInput)
    return $credentialValue.Password
}
if (-not $env:TENCENTCLOUD_SECRET_ID) { $env:TENCENTCLOUD_SECRET_ID = Read-SecretValue 'Tencent Cloud SecretId (hidden)' }
if (-not $env:TENCENTCLOUD_SECRET_KEY) { $env:TENCENTCLOUD_SECRET_KEY = Read-SecretValue 'Tencent Cloud SecretKey (hidden)' }
$env:SEARCHPRO_AUTH_MODE = 'tc3'
Write-Host 'Credentials are only in this process environment. No key file was written.'
& '.\scripts\run.ps1' -Port $Port
exit $LASTEXITCODE
