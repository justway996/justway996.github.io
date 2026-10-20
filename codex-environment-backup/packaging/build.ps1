param([string]$Python = 'python', [string]$BuildDependencies = '')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$env:PYTHONPATH = (Join-Path $taskRoot 'src')
if ($BuildDependencies) { $env:PYTHONPATH += ';' + $BuildDependencies }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $taskRoot '.test-work/pyinstaller-config'
$env:TMP = Join-Path $taskRoot '.test-work/build-temp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Path $env:TMP -Force | Out-Null
& $Python -m PyInstaller --noconfirm --onedir --name CodexEnvironmentBackup --paths src --collect-all cryptography --collect-data codex_backup --hidden-import tkinter packaging/entry.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& $Python -m PyInstaller --noconfirm --onedir --noconsole --name CodexEnvironmentBackupWorker --paths src --collect-all cryptography --collect-data codex_backup --hidden-import tkinter packaging/entry.py
if ($LASTEXITCODE -ne 0) { throw 'Background worker build failed' }
Copy-Item -LiteralPath dist/CodexEnvironmentBackupWorker/CodexEnvironmentBackupWorker.exe -Destination dist/CodexEnvironmentBackup/CodexEnvironmentBackupWorker.exe
Copy-Item -LiteralPath README.md -Destination dist/CodexEnvironmentBackup/README.md
Copy-Item -LiteralPath docs -Destination dist/CodexEnvironmentBackup/docs -Recurse
