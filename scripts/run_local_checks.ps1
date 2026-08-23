param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [string]$BackendPythonPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

if (-not $BackendPythonPath) {
    $BackendPythonPath = Join-Path $backendDir "venv\Scripts\python.exe"
}

function Write-Step {
    param([string]$Name)
    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
}

function Write-Field {
    param(
        [string]$Name,
        [AllowNull()]$Value
    )
    if ($null -eq $Value -or $Value -eq "") {
        Write-Host ("{0}: <empty>" -f $Name)
    } else {
        Write-Host ("{0}: {1}" -f $Name, $Value)
    }
}

function Assert-Value {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw "ASSERT FAILED: $Message"
    }
}

$script:Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$script:EvidenceDir = Join-Path $repoRoot "test_evidence\$Stamp"
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null

$gitSha = "<unknown>"
try {
    $gitSha = (git -C $repoRoot rev-parse HEAD).Trim()
} catch {
    $gitSha = "<git not available>"
}

$results = [System.Collections.Generic.List[object]]::new()

function Invoke-LoggedCommand {
    param(
        [string]$Executable,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$LogFileName
    )
    $logPath = Join-Path $script:EvidenceDir $LogFileName
    Push-Location $WorkingDirectory
    # Native stderr must not abort the pipeline; the exit code decides PASS/FAIL.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Executable @ArgumentList 2>&1 | Tee-Object -FilePath $logPath | Out-Null
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
        Pop-Location
    }
}

function Record-Result {
    param(
        [string]$Name,
        [int]$ExitCode,
        [string]$Artifact
    )
    $status = "PASS"
    if ($ExitCode -ne 0) {
        $status = "FAIL"
    }
    $results.Add([pscustomobject]@{
        Name = $Name
        Status = $status
        ExitCode = $ExitCode
        Artifact = $Artifact
    })
    Write-Host ("{0} {1} (exit={2})" -f $status, $Name, $ExitCode) -ForegroundColor $(if ($status -eq "PASS") { "Green" } else { "Red" })
}

Write-Host "Local verification checks"
Write-Field "RepoRoot" $repoRoot
Write-Field "GitSha" $gitSha
Write-Field "EvidenceDir" $EvidenceDir
Write-Field "Backend" $(if ($SkipBackend) { "skipped by -SkipBackend" } else { "enabled" })
Write-Field "Frontend" $(if ($SkipFrontend) { "skipped by -SkipFrontend" } else { "enabled" })

if (-not $SkipBackend) {
    Assert-Value (Test-Path -LiteralPath $BackendPythonPath -PathType Leaf) (
        "Backend python not found at '$BackendPythonPath'. Create backend\venv first or pass -BackendPythonPath."
    )

    Write-Step "1. Backend compileall"
    $code = Invoke-LoggedCommand -Executable $BackendPythonPath `
        -ArgumentList @("-m", "compileall", "app") `
        -WorkingDirectory $backendDir `
        -LogFileName "01-backend-compileall.txt"
    Record-Result -Name "backend compileall" -ExitCode $code -Artifact "01-backend-compileall.txt"

    Write-Step "2. Backend pytest"
    $junitPath = Join-Path $EvidenceDir "pytest-junit.xml"
    $code = Invoke-LoggedCommand -Executable $BackendPythonPath `
        -ArgumentList @("-m", "pytest", "--junitxml=$junitPath") `
        -WorkingDirectory $backendDir `
        -LogFileName "02-backend-pytest.txt"
    Record-Result -Name "backend pytest" -ExitCode $code -Artifact "02-backend-pytest.txt (+ pytest-junit.xml)"
}

if (-not $SkipFrontend) {
    Assert-Value (Test-Path -LiteralPath (Join-Path $frontendDir "package.json") -PathType Leaf) (
        "Frontend directory not found at '$frontendDir'."
    )
    Assert-Value (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules") -PathType Container) (
        "frontend\node_modules is missing. Run 'npm ci --ignore-scripts' inside frontend first."
    )

    Write-Step "3. Frontend contract tests"
    $code = Invoke-LoggedCommand -Executable "npm.cmd" `
        -ArgumentList @("run", "test:stage3-contract") `
        -WorkingDirectory $frontendDir `
        -LogFileName "03-frontend-contract.txt"
    Record-Result -Name "frontend contract tests" -ExitCode $code -Artifact "03-frontend-contract.txt"

    Write-Step "4. Frontend build"
    $code = Invoke-LoggedCommand -Executable "npm.cmd" `
        -ArgumentList @("run", "build") `
        -WorkingDirectory $frontendDir `
        -LogFileName "04-frontend-build.txt"
    Record-Result -Name "frontend build" -ExitCode $code -Artifact "04-frontend-build.txt"
}

$failedCount = @($results | Where-Object { $_.Status -eq "FAIL" }).Count
$overall = "PASS"
if ($failedCount -gt 0) {
    $overall = "FAILED"
}
if ($results.Count -eq 0) {
    $overall = "NOTHING RAN"
}

$summaryLines = [System.Collections.Generic.List[string]]::new()
[void]$summaryLines.Add("Local checks summary")
[void]$summaryLines.Add(("GeneratedAt: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
[void]$summaryLines.Add(("GitSha: {0}" -f $gitSha))
[void]$summaryLines.Add(("Overall: {0} ({1}/{2} steps passed)" -f $overall, ($results.Count - $failedCount), $results.Count))
[void]$summaryLines.Add("")
foreach ($result in $results) {
    [void]$summaryLines.Add(("[{0}] {1} -> test_evidence\{2}\{3}" -f $result.Status, $result.Name, $Stamp, $result.Artifact))
}
$summaryPath = Join-Path $EvidenceDir "summary.txt"
$summaryLines | Out-File -FilePath $summaryPath

Write-Host ""
Write-Host "== Summary ==" -ForegroundColor Cyan
foreach ($result in $results) {
    Write-Host ("[{0}] {1} -> {2}" -f $result.Status, $result.Name, (Join-Path $EvidenceDir $result.Artifact))
}
Write-Host ""

if ($overall -eq "PASS") {
    Write-Host "LOCAL CHECKS PASS" -ForegroundColor Green
    Write-Field "Summary" $summaryPath
    exit 0
}

Write-Host "LOCAL CHECKS FAILED" -ForegroundColor Red
Write-Field "Summary" $summaryPath
exit 1
