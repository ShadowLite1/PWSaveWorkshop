$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
    }
    & ./.venv/Scripts/python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & ./.venv/Scripts/python.exe -m PyInstaller --noconfirm ESW.spec
    if ($LASTEXITCODE -ne 0) { throw 'ESW build failed' }
    Write-Host 'Built dist/EspiritSaveWorkshop/EspiritSaveWorkshop.exe with its _internal folder'
} finally { Pop-Location }
