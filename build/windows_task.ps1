param([Parameter(Mandatory=$true)][ValidateSet('setup','deploy','desktop','serial','check','test')][string]$Task)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $packageRoot
$pythonExe = Join-Path $packageRoot '.venv\Scripts\python.exe'
function Invoke-Python {
    param([string[]]$PythonArgs)
    & $pythonExe @PythonArgs
    if ($LASTEXITCODE -ne 0) { throw ('Python command failed with exit code ' + $LASTEXITCODE) }
}
try {
    if ($Task -eq 'desktop') { & (Join-Path $packageRoot 'src\pc\install_desktop.ps1'); exit 0 }
    if ($Task -eq 'setup') {
        if (-not (Test-Path -LiteralPath $pythonExe)) {
            if (Get-Command py -ErrorAction SilentlyContinue) {
                & py -3.12 -m venv (Join-Path $packageRoot '.venv')
            } else {
                & python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Install Python 3.12"'
                if ($LASTEXITCODE -ne 0) { throw '请先安装 Python 3.12，再双击本文件。' }
                & python -m venv (Join-Path $packageRoot '.venv')
            }
            if ($LASTEXITCODE -ne 0) { throw '请先安装 Python 3.12（包含 py 启动器），再重试。' }
        }
        Invoke-Python -PythonArgs @('-m','pip','install','-r','requirements-pc.txt')
        Write-Host '电脑部署工具已准备好。下一步：检查 config.json，再运行 02_deploy.bat。' -ForegroundColor Green
        exit 0
    }
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw '请先运行 01_setup.bat。日常打开桌面应用不需要 Python。' }
    switch ($Task) {
        'deploy' { Invoke-Python -PythonArgs @('board/deploy.py') }
        'serial' { Invoke-Python -PythonArgs @('src/pc/serial_monitor.py') }
        'check' { Invoke-Python -PythonArgs @('board/check_live.py') }
        'test' {
            Invoke-Python -PythonArgs @('-m','pip','install','-r','requirements-test.txt')
            Invoke-Python -PythonArgs @('sim/verify_multi_targets.py')
            Invoke-Python -PythonArgs @('sim/verify_color_rules.py')
            Invoke-Python -PythonArgs @('sim/test_portability.py')
            Write-Host '模拟测试通过。结果在 data/results 文件夹；这不代表实物矿石鉴定准确率。' -ForegroundColor Green
        }
    }
} catch {
    Write-Host ('操作未完成：' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '请查看 README.md 和 docs/troubleshooting.md。'
    exit 1
}
