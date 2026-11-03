param(
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA 'B220OreVision\app'),
    [string]$DesktopDirectory = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sourceConfig = Join-Path $packageRoot 'config.json'
$config = Get-Content -LiteralPath $sourceConfig -Raw -Encoding UTF8 | ConvertFrom-Json
if ($config.host -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or $config.http_port -lt 1024 -or $config.http_port -gt 65535) { throw 'Check host and http_port in config.json.' }
New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $DesktopDirectory -Force | Out-Null
foreach ($name in @('b220_ore_app.exe', 'config.json')) {
    $existing = Join-Path $installDirectory $name
    if (Test-Path -LiteralPath $existing) {
        Copy-Item -LiteralPath $existing -Destination ($existing + '.bak.' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'b220_ore_app.exe') -Destination $installDirectory -Force
Copy-Item -LiteralPath $sourceConfig -Destination (Join-Path $installDirectory 'config.json') -Force
$desktop = $DesktopDirectory
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'B220 矿石输送视觉演示（提交版）.lnk'))
$shortcut.TargetPath = Join-Path $installDirectory 'b220_ore_app.exe'
$shortcut.WorkingDirectory = $installDirectory
$shortcut.IconLocation = $shortcut.TargetPath + ',0'
$shortcut.Description = '开发板矿石识别：双击打开，无需再次部署'
$shortcut.Save()
Write-Host '桌面入口已创建：B220 矿石输送视觉演示（提交版）' -ForegroundColor Green
Write-Host ('应用地址：http://' + $config.host + ':' + $config.http_port)
Write-Host '只更换电脑时，设好电脑以太网 IP 后运行本步骤即可，无需再次部署已配置的开发板。'
