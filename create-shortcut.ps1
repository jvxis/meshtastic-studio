param(
    [switch]$AllowWrites,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'
$meshPython = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $meshPython)) {
    throw 'Instale o app primeiro com start.ps1 ou pela instalacao manual do README.'
}
$meshDesktop = [Environment]::GetFolderPath('DesktopDirectory')
$meshShell = New-Object -ComObject WScript.Shell
$meshShortcut = $meshShell.CreateShortcut((Join-Path $meshDesktop 'Mesh Studio.lnk'))
$meshShortcut.TargetPath = $meshPython
$meshLauncher = Join-Path $PSScriptRoot 'launcher.py'
$meshShortcut.Arguments = '"' + $meshLauncher + '" --port ' + $Port
if ($AllowWrites) { $meshShortcut.Arguments += ' --allow-writes' }
$meshShortcut.WorkingDirectory = $PSScriptRoot
$meshShortcut.Description = 'Inicia o Mesh Studio se necessario e abre o app no navegador.'
$meshShortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',14'
$meshShortcut.WindowStyle = 7
$meshShortcut.Save()
Write-Host "Atalho criado: $(Join-Path $meshDesktop 'Mesh Studio.lnk')"
