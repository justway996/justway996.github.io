param(
    [Parameter(Mandatory=$true)][string]$Payload,
    [string]$Python='python',
    [string]$BuildDependencies='',
    [string]$OutputDirectory='dist'
)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPayload=(Resolve-Path -LiteralPath $Payload).Path
Set-Location -LiteralPath $taskRoot
$env:PYTHONPATH=Join-Path $taskRoot 'src'
if($BuildDependencies) { $env:PYTHONPATH+=';'+$BuildDependencies }
$env:PYINSTALLER_CONFIG_DIR=Join-Path $taskRoot '.test-work/pyinstaller-config'
$env:TMP=Join-Path $taskRoot '.test-work/build-temp'
$env:TEMP=$env:TMP
$taskInputs=Join-Path $taskRoot '.test-work/installer-input'
New-Item -ItemType Directory -Path $taskInputs -Force | Out-Null
Copy-Item -LiteralPath $taskPayload -Destination (Join-Path $taskInputs 'payload.zip')
$taskHash=(Get-FileHash -LiteralPath $taskPayload -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $taskInputs 'payload.sha256'),$taskHash,[Text.Encoding]::ASCII)
& $Python -m PyInstaller --noconfirm --onefile --noconsole --name CodexEnvironmentBackupSetup --distpath $OutputDirectory --paths src --hidden-import tkinter --add-data "$taskInputs/payload.zip;." --add-data "$taskInputs/payload.sha256;." packaging/installer_entry.py
if($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
$taskInstaller=Join-Path $OutputDirectory 'CodexEnvironmentBackupSetup.exe'
if((Get-Item -LiteralPath $taskInstaller).Length -gt 52428800) { throw 'Installer exceeds the verified cloud download limit' }
$taskChecksum=(Get-FileHash -LiteralPath $taskInstaller -Algorithm SHA256).Hash.ToLowerInvariant()+'  CodexEnvironmentBackupSetup.exe'
[IO.File]::WriteAllText((Join-Path $OutputDirectory 'SETUP-SHA256SUMS.txt'),$taskChecksum+"`n",[Text.Encoding]::ASCII)
