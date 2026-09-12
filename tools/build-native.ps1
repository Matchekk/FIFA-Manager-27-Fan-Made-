param([switch]$Resume,[switch]$OptimizeOffline,[string]$OutputName)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $visualStudio) { throw 'Visual Studio 2022 C++ build tools and Windows SDK required.' }
$msbuild = Join-Path $visualStudio 'MSBuild\Current\Bin\MSBuild.exe'
$shadow = Join-Path $root $(if ($OptimizeOffline) { 'build\upstream-optimized' } else { 'build\upstream' })
if ((Test-Path -LiteralPath $shadow) -and -not $Resume) { throw 'Shadow source already exists. Inspect, then use -Resume for an incremental build.' }
if (-not $Resume) {
New-Item -ItemType Directory -Path $shadow -Force | Out-Null
foreach ($part in @('generic','shared','fmapi','fifaapi')) {
    Copy-Item -LiteralPath (Join-Path $root "upstream\fifam\$part") -Destination $shadow -Recurse
}
# Headless adapter for the offline tool only. Upstream reports errors in modal
# dialogs and continues; fail fast instead. This is never injected into the game.
@'
#pragma once
#include <Windows.h>
#include <cstdio>
#include <stdexcept>
#include <string>
template<class... Args> bool Error(std::string const& format, Args... args) {
    char text[4096]{}; sprintf_s(text, format.c_str(), args...);
    std::fprintf(stderr, "FIFAM error: %s\n", text);
    throw std::runtime_error("Upstream FIFAM reader error (see preceding log)");
}
template<class... Args> bool Error(std::wstring const& format, Args... args) {
    wchar_t text[4096]{}; swprintf_s(text, format.c_str(), args...);
    std::fwprintf(stderr, L"FIFAM error: %ls\n", text);
    throw std::runtime_error("Upstream FIFAM reader error (see preceding log)");
}
inline bool Message(std::string const& text) { std::fprintf(stderr, "%s\n", text.c_str()); return true; }
inline bool Message(std::wstring const& text) { std::fwprintf(stderr, L"%ls\n", text.c_str()); return true; }
'@ | Set-Content -LiteralPath (Join-Path $shadow 'generic\Error.h') -Encoding UTF8
}
foreach ($project in @('generic','fmapi','fifaapi')) {
    if ($OptimizeOffline) {
        $projectFile = Join-Path $shadow "$project\$project.vcxproj"
        $projectText = [IO.File]::ReadAllText($projectFile).Replace('<Optimization>Disabled</Optimization>','<Optimization>MaxSpeed</Optimization>')
        [IO.File]::WriteAllText($projectFile,$projectText)
    }
    $log = Join-Path $root ".agent_tmp\build-$project.log"
    & $msbuild (Join-Path $shadow "$project\$project.vcxproj") /m:2 /v:minimal /nologo /p:Configuration=Release /p:Platform=Win32 "/p:SolutionDir=$shadow\" > $log 2>&1
    if ($LASTEXITCODE -ne 0) { Get-Content -LiteralPath $log -Tail 15; throw "Build failed: $project" }
}
$compiler = Get-ChildItem -LiteralPath (Join-Path $visualStudio 'VC\Tools\MSVC') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$sdk = Get-ChildItem -LiteralPath (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$sdkRoot = Split-Path (Split-Path $sdk.FullName -Parent) -Parent
$env:INCLUDE = @("$($compiler.FullName)\include", "$($sdk.FullName)\ucrt", "$($sdk.FullName)\shared", "$($sdk.FullName)\um", "$($sdk.FullName)\winrt") -join ';'
$env:LIB = @("$($compiler.FullName)\lib\x86", "$sdkRoot\Lib\$($sdk.Name)\ucrt\x86", "$sdkRoot\Lib\$($sdk.Name)\um\x86") -join ';'
$cl = Join-Path $compiler.FullName 'bin\Hostx64\x86\cl.exe'
Push-Location (Join-Path $root 'build')
try {
    $binaryName = if ($OutputName) { $OutputName } elseif ($OptimizeOffline) { 'fm27-db-probe-optimized.exe' } else { 'fm27-db-probe.exe' }
    if ([IO.Path]::GetFileName($binaryName) -ne $binaryName -or [IO.Path]::GetExtension($binaryName) -ne '.exe') {
        throw 'OutputName must be a leaf .exe filename.'
    }
    & $cl /nologo /std:c++latest /EHsc /W4 /WX /MT /D_CRT_SECURE_NO_WARNINGS /DWIN32_LEAN_AND_MEAN /external:W0 "/external:I$shadow\generic" "/external:I$shadow\fmapi" "/external:I$shadow\shared" (Join-Path $root 'src\native\db_probe.cpp') "/Fe:$binaryName" /link "/LIBPATH:$shadow\output\libs" fmapi.lib generic.lib user32.lib bcrypt.lib /LARGEADDRESSAWARE > (Join-Path $root '.agent_tmp\build-probe.log') 2>&1
    if ($LASTEXITCODE -ne 0) { Get-Content (Join-Path $root '.agent_tmp\build-probe.log') -Tail 15; throw 'Bridge compilation failed.' }
} finally { Pop-Location }
$nativeSourceHashes = [ordered]@{}
$nativeInputs = @((Get-ChildItem -LiteralPath (Join-Path $root 'src\native') -File | Where-Object { $_.Extension -in @('.cpp','.h') }))
$nativeInputs += Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Filter 'native*.h' -File
$nativeInputs += Get-Item -LiteralPath $PSCommandPath
foreach ($nativeInput in ($nativeInputs | Sort-Object FullName)) {
    $nativeRelativePath = [IO.Path]::GetRelativePath($root,$nativeInput.FullName)
    $nativeSourceHashes[$nativeRelativePath] = (Get-FileHash -LiteralPath $nativeInput.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
@{ status='PASS'; binary_sha256=(Get-FileHash -LiteralPath (Join-Path $root "build\$binaryName") -Algorithm SHA256).Hash.ToLowerInvariant();
   built_at=[DateTime]::UtcNow.ToString('o'); source_sha256=$nativeSourceHashes; optimized_libraries=[bool]$OptimizeOffline
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $root "build\$binaryName.build.json") -Encoding UTF8
Write-Output "Built offline FIFAM bridge: $binaryName. This does not optimize Manager.exe."
