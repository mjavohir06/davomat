# Yangi versiyani hamkasblarga chiqarish: davomat.pyw dagi VERSIYA ni oshiring, yigish.ps1 ni ishga tushiring,
# keyin shu skript: GitHub'da reliz yaratadi va Davomat.exe ni yuklaydi. Hamkasblardagi ilova 12 soat ichida
# (yoki ishga tushganda) yangilanishni taklif qiladi.
#   .\chiqarish.ps1 "Nima o'zgardi (qisqa)"
param([string]$izoh = "")
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir
$m = Select-String -Path davomat.pyw -Pattern '^VERSIYA = "([\d.]+)"' | Select-Object -First 1
if (-not $m) { throw "davomat.pyw da VERSIYA topilmadi" }
$v = $m.Matches[0].Groups[1].Value
if (-not (Test-Path "dist\Davomat.exe")) { throw "Avval yigish.ps1 ni ishga tushiring" }
if ((Get-Item "dist\Davomat.exe").LastWriteTime -lt (Get-Item "davomat.pyw").LastWriteTime) {
    throw "dist\Davomat.exe davomat.pyw dan eski — avval yigish.ps1 ni qayta ishga tushiring"
}
git add -A
git commit -m "Davomat $v" 2>$null
git push
if (-not $izoh) { $izoh = "Davomat $v" }
gh release create "v$v" "dist\Davomat.exe" --title "Davomat $v" --notes $izoh
Write-Output "Chiqarildi: v$v"
