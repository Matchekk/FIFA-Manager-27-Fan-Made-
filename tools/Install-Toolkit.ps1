param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'FM27CommunityToolkit'))
$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot -Parent
$target = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
if (Test-Path -LiteralPath $target) { throw 'Destination already exists. Use a new empty destination; existing files will not be overwritten.' }
$ancestor = [IO.DirectoryInfo]::new($target)
while ($null -ne $ancestor) {
    if (Test-Path -LiteralPath (Join-Path $ancestor.FullName 'Manager.exe')) { throw 'Install the toolkit outside the game directory.' }
    $ancestor = $ancestor.Parent
}
$package = Get-Content -LiteralPath (Join-Path $source 'package-manifest.json') -Raw | ConvertFrom-Json
$records = @()
# Preflight every file before creating the destination. No backups are necessary
# because this installer never overwrites an existing directory or file.
foreach ($file in $package.files) {
    $relative = [string]$file.path
    $inputPath = [IO.Path]::GetFullPath((Join-Path $source $relative))
    $outputPath = [IO.Path]::GetFullPath((Join-Path $target $relative))
    if (-not $inputPath.StartsWith($source + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not $outputPath.StartsWith($target + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe manifest path.' }
    if ((Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw "Package hash mismatch: $relative" }
    $records += @{path=$relative; sha256=$file.sha256}
}
New-Item -ItemType Directory -Path $target | Out-Null
@{schema_version=1; kind='FM27_DIAGNOSTIC_TOOLKIT'; root=$target; files=$records} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $target 'uninstall-manifest.json') -Encoding UTF8
foreach ($file in $records) {
    $outputPath = Join-Path $target $file.path
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $file.path) -Destination $outputPath
}
Write-Output "Toolkit installed at $target. No game/database files installed or changed."
