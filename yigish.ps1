# Davomat.exe ni yig'ish (PyInstaller, bitta fayl). Natija: dist\Davomat.exe
# Hamkasbga shu bitta faylni bering — birinchi ochilganda o'zini o'rnatadi (admin huquqi kerak emas).
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir
$py = Join-Path $dir ".venv\Scripts\python.exe"

# UI Automation turlari (comtypes.gen) oldindan yaratilsin — exe ichiga kirishi uchun
& $py -c "import comtypes.client as c; c.GetModule('UIAutomationCore.dll')"

& $py -m PyInstaller --noconfirm --clean --onefile --windowed --name Davomat --icon davomat.ico `
    --hidden-import pystray._win32 `
    --collect-submodules comtypes.gen `
    --hidden-import comtypes.gen.UIAutomationClient `
    --exclude-module numpy --exclude-module matplotlib `
    davomat.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller xato bilan tugadi" }

# yig'ilgan exe ichidagi qismlarni sinash (o'rnatmaydi)
$sinov = Join-Path $env:TEMP "davomat_sinov.json"
Remove-Item $sinov -ErrorAction SilentlyContinue
Start-Process -FilePath "dist\Davomat.exe" -ArgumentList "--sinov", "`"$sinov`"" -Wait
Get-Content $sinov -Encoding UTF8
$v = (Get-Item "dist\Davomat.exe").Length / 1MB
Write-Output ("dist\Davomat.exe — {0:N1} MB" -f $v)
