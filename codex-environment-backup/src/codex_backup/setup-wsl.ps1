param([ValidateSet('Inspect','Enable')][string]$Action='Inspect', [string]$Msi='', [string]$ResultFile='')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules')+';'+$env:PSModulePath
$ProgressPreference='SilentlyContinue'
if ($Action -eq 'Inspect') {
    $os=Get-CimInstance Win32_OperatingSystem
    $enabled=$true
    foreach($name in @('VirtualMachinePlatform','Microsoft-Windows-Subsystem-Linux')) {
        $feature=Get-CimInstance Win32_OptionalFeature -Filter ("Name='"+$name+"'")
        if(-not $feature -or $feature.InstallState -ne 1) { $enabled=$false }
    }
    @{supported=([int]$os.BuildNumber -ge 22000 -and [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -eq 'X64'); system_ready=$enabled; boot_id=$os.LastBootUpTime.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress
    exit 0
}
$result=@{state='failed'; error_code='SYSTEM_SETUP_FAILED'}
try {
    $needsRestart=$false
    if($Msi) {
        $signature=Get-AuthenticodeSignature -LiteralPath $Msi
        if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
            $result.error_code='SIGNATURE_INVALID'
            throw 'Invalid Microsoft signature'
        }
        $process=Start-Process -FilePath "$env:WINDIR/System32/msiexec.exe" -ArgumentList @('/i',('"'+$Msi+'"'),'/qn','/norestart') -Wait -PassThru -WindowStyle Hidden
        if($process.ExitCode -notin @(0,3010)) { throw 'MSI failed' }
        if($process.ExitCode -eq 3010) { $needsRestart=$true }
    }
    foreach($name in @('VirtualMachinePlatform','Microsoft-Windows-Subsystem-Linux')) {
        $feature=Get-WindowsOptionalFeature -Online -FeatureName $name
        if($feature.State -ne 'Enabled') {
            $process=Start-Process -FilePath "$env:WINDIR/System32/dism.exe" -ArgumentList @('/online','/enable-feature',('/featurename:'+$name),'/all','/norestart') -Wait -PassThru -WindowStyle Hidden
            if($process.ExitCode -notin @(0,3010)) { throw 'Feature setup failed' }
            $needsRestart=$true
        }
    }
    $result=@{state=$(if($needsRestart){'restart_required'}else{'ready'})}
} catch { }
if($ResultFile) {
    [IO.File]::WriteAllText($ResultFile,($result | ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
}
if($result.state -eq 'failed') { exit 1 }
exit 0
