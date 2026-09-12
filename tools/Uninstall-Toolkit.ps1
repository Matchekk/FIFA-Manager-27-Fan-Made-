param([Parameter(Mandatory=$true)][string]$Installation)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Installation).Path.TrimEnd('\')
if (Test-Path -LiteralPath (Join-Path $root 'Manager.exe')) { throw 'Refusing game root.' }
$manifestPath = Join-Path $root 'uninstall-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.kind -ne 'FM27_DIAGNOSTIC_TOOLKIT' -or $manifest.root -ne $root) { throw 'Wrong uninstall manifest.' }
$targets = @()
foreach ($file in $manifest.files) {
    $target = [IO.Path]::GetFullPath((Join-Path $root $file.path))
    if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall path.' }
    # Reject reparse-point components so lexical containment cannot escape via a junction.
    $current = [IO.FileInfo]::new($target).Directory
    while ($null -ne $current -and $current.FullName.Length -ge $root.Length) {
        if ($current.Exists -and ($current.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse point in uninstall path.' }
        $current = $current.Parent
    }
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing linked uninstall file.' }
        $targets += @{path=$target; sha256=$file.sha256}
    }
}
$preserved = @()
foreach ($file in $targets) {
    if ((Get-FileHash -LiteralPath $file.path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256) {
        Remove-Item -LiteralPath $file.path
    } else { $preserved += $file.path }
}
if ($preserved.Count -eq 0) { Remove-Item -LiteralPath $manifestPath }
@{removed_toolkit_files=$targets.Count-$preserved.Count; preserved_modified_files=$preserved;
  note='Unrelated files and empty directories are preserved. No recursive deletion.'} | ConvertTo-Json -Depth 4
