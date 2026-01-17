$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPath = Join-Path $repoRoot ".venv_clean"
$requirementsPath = Join-Path $repoRoot "backend\\requirements.txt"

Write-Host "Repo root: $repoRoot"
Write-Host "Venv path: $venvPath"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating venv: python -m venv $venvPath"
    python -m venv $venvPath
} else {
    Write-Host "Venv already exists, reusing: $venvPath"
}

$activateScript = Join-Path $venvPath "Scripts\\Activate.ps1"
Write-Host "Activating venv: $activateScript"
& $activateScript

Write-Host "Upgrading pip: python -m pip install -U pip"
python -m pip install -U pip

Write-Host "Installing requirements: pip install -r $requirementsPath"
pip install -r $requirementsPath

Write-Host "Starting backend: uvicorn app.main:app --reload"
Push-Location (Join-Path $repoRoot "backend")
uvicorn app.main:app --reload
Pop-Location
