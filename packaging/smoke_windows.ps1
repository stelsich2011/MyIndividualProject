param()
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskSmokeRoot = Join-Path $taskRoot 'data/processed/release_smoke'
New-Item -ItemType Directory -Force -Path $taskSmokeRoot | Out-Null
$taskInstallPath = Join-Path $taskSmokeRoot ('Проверка установки ' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$taskResolvedInstall = [IO.Path]::GetFullPath($taskInstallPath)
if (-not $taskResolvedInstall.StartsWith(([IO.Path]::GetFullPath($taskSmokeRoot) + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Каталог проверки выходит за пределы data/processed/release_smoke'
}
$taskSetup = Join-Path $taskRoot 'dist/installer/OGEChecker-Setup.exe'
$taskArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/NOICONS',
    ('/DIR="' + $taskResolvedInstall + '"'), ('/LOG="' + (Join-Path $taskSmokeRoot 'install.log') + '"'))
$taskInstallProcess = Start-Process -FilePath $taskSetup -ArgumentList $taskArguments -WindowStyle Hidden -Wait -PassThru
if ($taskInstallProcess.ExitCode -ne 0) { throw ('Установка: ' + $taskInstallProcess.ExitCode) }
try {
    $env:OGE_MODEL_DIR = Join-Path $taskSmokeRoot 'installed_empty_cache'
    $env:HTTP_PROXY = 'http://127.0.0.1:9'
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    $env:ALL_PROXY = 'http://127.0.0.1:9'
    $taskReport = Join-Path $taskSmokeRoot 'installed.json'
    $taskPdf = Join-Path $taskRoot 'data/raw/full_pdf.pdf'
    $taskAppArguments = @('--self-test', '--self-test-pdf', ('"' + $taskPdf + '"'), '--self-test-pages', '1,36,38,62',
                         '--self-test-report', ('"' + $taskReport + '"'))
    $taskApplication = Start-Process -FilePath (Join-Path $taskResolvedInstall 'OGEChecker.exe') -ArgumentList $taskAppArguments -WindowStyle Hidden -Wait -PassThru
    if ($taskApplication.ExitCode -ne 0) { throw ('Приложение: ' + $taskApplication.ExitCode) }
    $taskResult = Get-Content -LiteralPath $taskReport -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $taskResult.ok -or -not $taskResult.pdf_checked) { throw 'Самопроверка не пройдена' }
    if (-not $taskResult.model_path.StartsWith($taskResolvedInstall, [StringComparison]::OrdinalIgnoreCase)) { throw 'Использована внешняя модель' }
    Get-Content -LiteralPath $taskReport -Encoding UTF8
} finally {
    $taskUninstaller = Join-Path $taskResolvedInstall 'unins000.exe'
    if (Test-Path -LiteralPath $taskUninstaller) {
        $taskUninstallProcess = Start-Process -FilePath $taskUninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -WindowStyle Hidden -Wait -PassThru
        if ($taskUninstallProcess.ExitCode -ne 0) { throw ('Удаление тестовой установки: ' + $taskUninstallProcess.ExitCode) }
    }
}
