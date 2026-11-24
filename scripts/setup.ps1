$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$env:PYTHONUTF8 = "1"

function Invoke-NativeChecked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python 3.12 is required. Install Python and make the py launcher available."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js 20+ and npm are required."
}

Push-Location $root
try {
    Invoke-NativeChecked "py" @("-3.12", "--version")
    if (-not (Test-Path $python)) {
        Invoke-NativeChecked "py" @("-3.12", "-m", "venv", $venv)
    }
    Invoke-NativeChecked $python @("-m", "ensurepip", "--upgrade")
    Invoke-NativeChecked $python @("-m", "pip", "install", "-r", "backend/requirements.txt")
    Invoke-NativeChecked "npm" @("--prefix", "frontend", "ci")
    Invoke-NativeChecked "npm" @("--prefix", "frontend", "run", "build")
    Invoke-NativeChecked $python @("demo/run_demo.py")
    Invoke-NativeChecked $python @("-m", "pytest", "backend/tests", "-q")
} finally {
    Pop-Location
}
