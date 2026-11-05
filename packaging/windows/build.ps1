# Compila el ejecutable y el instalador de Windows.
# Uso: powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $raiz

Write-Host "== Dependencias ==" -ForegroundColor Cyan
python scripts\instalar_dependencias.py
if ($LASTEXITCODE -ne 0) { throw "Fallo al preparar las dependencias" }

python -m pip install -r requirements-dev.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Fallo al instalar los paquetes de Python" }

Write-Host "== PyInstaller ==" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --windowed `
    --name Descargador `
    --icon "assets\icono.ico" `
    --add-binary "bin\yt-dlp.exe;bin" `
    --add-binary "bin\ffmpeg.exe;bin" `
    --add-binary "bin\ffprobe.exe;bin" `
    --collect-all quickjs `
    --contents-directory . `
    --distpath dist --workpath build `
    Barra.pyw
if ($LASTEXITCODE -ne 0) { throw "Fallo PyInstaller" }

Write-Host "== Inno Setup ==" -ForegroundColor Cyan
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    throw "No encontre Inno Setup 6. Instalalo desde https://jrsoftware.org/isdl.php"
}

& $iscc "packaging\windows\instalador.iss"
if ($LASTEXITCODE -ne 0) { throw "Fallo Inno Setup" }

Write-Host ""
Write-Host "Listo. Instalador en: instaladores\" -ForegroundColor Green
Get-ChildItem "instaladores\*.exe" | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
