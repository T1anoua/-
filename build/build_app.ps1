$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Install .NET Framework 4.x developer tools, or use the supplied b220_ore_app.exe.' }
$sourceDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\pc'
$output = Join-Path $sourceDirectory 'b220_ore_app.exe'
$arguments = @('/nologo', '/target:winexe', '/optimize+', '/utf8output',
    '/reference:System.Windows.Forms.dll', '/reference:System.Web.Extensions.dll',
    ('/win32icon:' + (Join-Path $sourceDirectory 'ore_app.ico')),
    ('/resource:' + (Join-Path $sourceDirectory 'launcher.html') + ',OreApp.StartPage'),
    ('/out:' + $output), (Join-Path $sourceDirectory 'ore_app_launcher.cs'))
& $compiler @arguments
if ($LASTEXITCODE -ne 0) { throw 'C# compiler failed.' }
Write-Host "Built: $output"
