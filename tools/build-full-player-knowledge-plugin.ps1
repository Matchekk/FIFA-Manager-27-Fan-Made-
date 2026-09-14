param(
    [string]$Output = "data/qol/full-player-knowledge/plugins/FM27.FullPlayerKnowledge.asi"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root "src/plugins/full_player_knowledge/full_player_knowledge.cpp"
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $root $Output))
$buildDir = Join-Path $root "build/full-player-knowledge"
$vsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path -LiteralPath $vsDevCmd)) { throw "Visual Studio Build Tools not found" }
New-Item -ItemType Directory -Force -Path $buildDir,(Split-Path -Parent $outputPath) | Out-Null
$commandFile = Join-Path $buildDir "compile.cmd"
@(
    '@echo off'
    ('call "{0}" -arch=x86 -host_arch=x64 >nul' -f $vsDevCmd)
    ('cl /nologo /std:c++17 /O2 /MT /EHsc /W4 /WX /LD /Fo"{0}\\" "{1}" /link /NOLOGO /Brepro /OUT:"{2}"' -f $buildDir,$source,$outputPath)
) | Set-Content -LiteralPath $commandFile -Encoding Ascii
& cmd.exe /d /c $commandFile
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputPath)) { throw "x86 plugin build failed" }
$bytes = [System.IO.File]::ReadAllBytes($outputPath)
$peOffset = [BitConverter]::ToInt32($bytes, 0x3c)
$machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
if ($machine -ne 0x14c) { throw ('Expected x86 PE machine 0x14c, got 0x{0:x}' -f $machine) }
Get-FileHash -LiteralPath $outputPath -Algorithm SHA256
