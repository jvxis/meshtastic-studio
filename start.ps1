param(
    [switch]$AllowWrites,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765,
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
$meshRoot = $PSScriptRoot
$meshPython = Join-Path $meshRoot '.venv/Scripts/python.exe'
$meshMarker = Join-Path $meshRoot '.venv/mesh-studio-requirements.sha256'
$meshRequirements = Join-Path $meshRoot 'requirements.txt'
$meshRequirementsHash = (Get-FileHash -LiteralPath $meshRequirements -Algorithm SHA256).Hash
Push-Location -LiteralPath $meshRoot
try {
    if (-not (Test-Path -LiteralPath $meshPython)) {
        python -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)"
        if ($LASTEXITCODE -ne 0) { throw 'Use Python 3.11 a 3.14 para instalar o Mesh Studio.' }
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python.' }
        $Install = $true
    }
    if (-not (Test-Path -LiteralPath $meshMarker)) {
        $Install = $true
    } elseif ((Get-Content -LiteralPath $meshMarker -Raw).Trim() -ne $meshRequirementsHash) {
        $Install = $true
    }
    if ($Install) {
        & $meshPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
        $meshRequirementsHash | Set-Content -LiteralPath $meshMarker -Encoding ASCII
    }
    $env:MESH_ALLOW_WRITES = if ($AllowWrites) { '1' } else { '0' }
    Write-Host "Mesh Studio: http://127.0.0.1:$Port"
    Write-Host $(if ($AllowWrites) { 'Gravação habilitada. Cada aplicação exige revisão na interface.' } else { 'Somente leitura. Gravação real bloqueada no servidor.' })
    & $meshPython -m uvicorn server.app:app --host 127.0.0.1 --port $Port --no-access-log
} finally {
    Pop-Location
}
