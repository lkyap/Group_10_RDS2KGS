param(
    [switch]$SkipRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Ensure-Command {
    param(
        [string]$Name
    )
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH. Please install it and try again."
    }
}

function Invoke-Step {
    param(
        [string]$Description,
        [ScriptBlock]$Action
    )
    Write-Host ""
    Write-Host "=== $Description ==="
    & $Action
    Write-Host "=== Completed: $Description ==="
}

Ensure-Command -Name 'python'
Ensure-Command -Name 'npm'

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$venvPythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"

Invoke-Step -Description "Creating/updating Python virtual environment" -Action {
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating .venv using system Python..."
        python -m venv .venv
    } else {
        Write-Host "Virtual environment already exists; reusing."
    }

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Failed to install Python requirements." }
}

$yfilesDir = Join-Path $repoRoot "yfiles-vue-integration-basic-master"
$yfilesPackage = Get-ChildItem -Path (Join-Path $yfilesDir "yfiles-*.tgz") -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $yfilesPackage) {
    Write-Warning "No yFiles *.tgz package found under yfiles-vue-integration-basic-master. Replace the placeholder with your licensed package before running."
}

Invoke-Step -Description "Installing Node dependencies" -Action {
    Push-Location $yfilesDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    } finally {
        Pop-Location
    }
}

Invoke-Step -Description "Building yFiles front-end" -Action {
    Push-Location $yfilesDir
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
    } finally {
        Pop-Location
    }
}

if ($SkipRun) {
    Write-Host ""
    Write-Host "Setup completed. You can now run run_end_to_end.bat when ready."
    return
}

Write-Host ""
Write-Host "Launching run_end_to_end.bat ..."
& (Join-Path $repoRoot "run_end_to_end.bat")
Write-Host "If the UI window did not appear, check the console output and run run_end_to_end.bat manually."
