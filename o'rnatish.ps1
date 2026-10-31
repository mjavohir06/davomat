# Davomat: Windows ishga tushganda avtomatik ochilishi (Startup) va ish stoli yorlig'i.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $dir ".venv\Scripts\pythonw.exe"
$app = Join-Path $dir "davomat.pyw"
$sh = New-Object -ComObject WScript.Shell
foreach ($lnk in @(
    (Join-Path ([Environment]::GetFolderPath("Startup")) "Davomat.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Davomat hisoboti.lnk"))) {
    $s = $sh.CreateShortcut($lnk)
    $s.TargetPath = $pyw
    $s.Arguments = "`"$app`""
    $s.WorkingDirectory = $dir
    $s.Description = "Kunlik hisobotni to'ldirib Telegram guruhga yuborish"
    $s.Save()
    Write-Output "Yorliq: $lnk"
}
# Soat yonidagi belgi doim ko'rinsin ("^" ichiga yashirinmasin). Windows 11: belgi kamida bir marta chiqqan bo'lishi kerak.
Get-ChildItem "HKCU:\Control Panel\NotifyIconSettings" -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Get-ItemProperty $_.PSPath
    if ($p.ExecutablePath -like "*pythonw.exe") {
        Set-ItemProperty $_.PSPath -Name IsPromoted -Value 1 -Type DWord
        Write-Output "Tray belgisi doim ko'rinadi: $($p.ExecutablePath)"
    }
}
