# 전체 화면 스크린샷 → PNG 저장
# 사용: powershell -ExecutionPolicy Bypass -File screenshot.ps1 [출력경로]

param(
    [string]$OutputPath = "C:\Users\yijae\AppData\Local\Temp\claude_screenshot.png",
    [string]$Mode = "primary"  # primary | all | left | right
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if ($Mode -eq "all") {
    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $left = $vs.Left; $top = $vs.Top; $width = $vs.Width; $height = $vs.Height
} elseif ($Mode -eq "left") {
    $screens = [System.Windows.Forms.Screen]::AllScreens
    $target = $screens | Sort-Object { $_.Bounds.Left } | Select-Object -First 1
    $b = $target.Bounds
    $left = $b.Left; $top = $b.Top; $width = $b.Width; $height = $b.Height
} elseif ($Mode -eq "right") {
    $screens = [System.Windows.Forms.Screen]::AllScreens
    $target = $screens | Sort-Object { $_.Bounds.Left } -Descending | Select-Object -First 1
    $b = $target.Bounds
    $left = $b.Left; $top = $b.Top; $width = $b.Width; $height = $b.Height
} else {
    $p = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $left = $p.Left; $top = $p.Top; $width = $p.Width; $height = $p.Height
}

$bmp = New-Object System.Drawing.Bitmap($width, $height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($left, $top, 0, 0, (New-Object System.Drawing.Size($width, $height)))
$bmp.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()

Write-Host "OK $OutputPath $($width)x$($height)"
